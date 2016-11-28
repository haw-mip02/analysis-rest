# -*- coding: utf-8 -*-
"""
===================================
Analysis Rest Service

...
===================================
"""
import calendar
import os
import logging
import time
import numpy as np
import redis
from collections import defaultdict
from hdbscan import HDBSCAN
from sklearn.preprocessing import StandardScaler
from bson.son import SON
from datetime import datetime
from flask import Flask, jsonify, abort
from flask_cors import CORS, cross_origin
from pymongo import MongoClient, GEO2D, ASCENDING, DESCENDING
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA


# Sensible logging format
# TODO: proper setup for debug and release mode (also see app.run(debug...))
logging.basicConfig(format='%(asctime)s [%(levelname)s]: %(message)s', level=logging.DEBUG)

# Limit the amount of returned tweets
SEARCH_QUERY_RESULT_LIMIT = 5000
DESIRED_CLUSTER_COUNT = 5

class ProgressStatus(Enum):
    NEW = 'NEW'
    IN_PROGRESS = 'IN_PROGRESS'
	DONE = 'DONE'

def connect_to_and_setup_database():
	while True:
		try:
			addr = os.getenv('MONGODB_PORT_27017_TCP_ADDR', 'localhost')
			port = os.getenv('MONGODB_PORT_27017_TCP_PORT', '27017')
			passwd = os.getenv('MONGODB_PASS', 'supertopsecret')
			client = MongoClient('mongodb://analysis:' + passwd + '@' + addr + ':' + port + '/analysis')
			db = client.analysis
			db.tweets.ensure_index([("loc", GEO2D)])
			db.tweets.ensure_index([("created_at", ASCENDING)])
			logging.info("Connected to database: mongodb://%s:%s/analysis", addr, port)
			return client, db
		except Exception as error:
			logging.error(repr(error))
			time.sleep(2) # wait with the retry, database is possibly starting up

def connect_to_and_setup_cache():
	while True:
		try:
			addr = os.getenv('REDIS_PORT_6379_TCP_ADDR', 'localhost')
			port = int(os.getenv('REDIS_PORT_6379_TCP_PORT', '6379'))
			cache = redis.StrictRedis(host=addr, port=port, db=0)
			return cache
		except Exception as error:
			logging.error(repr(error))
			time.sleep(2) # wait with the retry, redis is possibly starting up

def save_response_in_cache(query_key, response):
	json = jsonify(response)
	cache.set(query, json)

def calc_location_hash(lat, lng): # simple hashing funktion for the location hashmap (used by clustering)
	return hash((round(lat,8), round(lng,8)))

def preprocess_data(data): # create location hashmap and create the numpy location array
	location_map = {}
	locations = []
	for tweet in data:
		lat, lng = tweet['loc'][0], tweet['loc'][1]
		location_map[calc_location_hash(lat, lng)] = tweet
		locations.append([lat, lng])
		del tweet['created_at'] # remove unimport information
		# NOTE: date is in UTC to get timestamp do something like this: calendar.timegm(dt.utctimetuple())
	return location_map, np.array(locations)

def create_cluster(cache_query_key, response, cluster, location_map):
	response['status'] = ProgressStatus.IN_PROGRESS
	save_response_in_cache(cache_query_key, response)
	location_map, locations = preprocess_data(results)

	clusters = calc_clusters(locations)
	for label in clusters:
		word_conns, word_values, word_polarity, center = analyse_cluster(clusters[label], location_map)
		# TODO: filter values, polarities and connections, e.g. trim to important details
		response['clusters'].append({ 'words': word_values, 'polarities': word_polarity, 'connections': word_conns, 'center': center })
	response['status'] = ProgressStatus.DONE
	save_response_in_cache(cache_query_key, response)

def calc_clusters(locations): # find the clusters
	#hdb = HDBSCAN(min_cluster_size=10).fit(locations)
	kmeans = KMeans(init='random', n_clusters=DESIRED_CLUSTER_COUNT, n_init=1).fit(locations)
	#labels = hdb.labels_
	labels = kmeans.labels_
	n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
	clusters = {}
	unique_labels = set(labels)
	for k in unique_labels:
		if not k == -1:
			clusters[k] = np.stack((locations[labels == k, 0], locations[labels == k, 1]), axis=-1)
	return clusters

def analyse_cluster(cluster, location_map):
	word_conns = {} # maps connections between words
	word_popularity = defaultdict(int) # essentially frequency of word usage
	word_polarity = defaultdict(int) # polarity scoring of the word across all the usages
	center = [0.0, 0.0]
	center_count = 0

	for loc in cluster: # for each location in cluster
		# add location to center count calculation
		center[0] += loc[0] # NOTE: a possible improvement would be to use outlier scores or the probability to
		center[1] += loc[1] #       represent the center of the cluster more accurately
		center_count += 1
		# get the tweet
		tweet = location_map[calc_location_hash(loc[0], loc[1])]
		for word in tweet['words']: # for each word increase popularity and polarity
			word_popularity[word] += 1
			word_polarity[word] += tweet['polarity'] + tweet['retweet_count'] + tweet['favorite_count']
			if not word in word_conns: # create the connection dictionary for the word if it doesnt exist
				word_conns[word] = defaultdict(int)
			# iterate over all other words and increment the connections
			for other in tweet['words']:
				if other != word:
					word_conns[word][other] += 1
	# to get a popularity scoring between -1 and 1 divide by the popularity
	for word, popularity in word_popularity.items():
		word_polarity[word] /= popularity
	# calculate the center
	center[0] /= center_count
	center[1] /= center_count
	return word_conns, word_popularity, word_polarity, center


client, db = connect_to_and_setup_database()
cache = connect_to_and_setup_cache()
app = Flask(__name__)
cors = CORS(app, resources={r"/analysis/*": {'origins': '*'}})

@app.route('/')
def index(): # default path to quickly curl/wget and test if running
	return 'Analysis REST-DB-Frontend running!'

@app.route('/analysis/v1.0/search/<string:latitude>/<string:longitude>/<string:radius>/<string:start>/<string:end>', methods=['GET'])
def search_radius(latitude, longitude, radius, start, end):
	try: # flask float converter cannot handle negative floats by default, so just use strings and internal python conversion
		# check cache first
		cache_query_key = '%s/%s/%s/%s/%s' % (latitude, longitude, radius, start, end)
		cached = cache.get(cache_query_key)
		if cached:
			return cached

		# if not cached process as usual
		latitude, longitude, radius = float(latitude), float(longitude), float(radius)
		start = datetime.utcfromtimestamp(float(start))
		end = datetime.utcfromtimestamp(float(end))
		# TODO: check if timespan is to big to process
		query = { 'created_at': { '$gte': start, '$lt': end }, 'loc': SON([("$near", [longitude, latitude]), ("$maxDistance", radius)]) }
		#
		response = { 'query': {'lat': latitude, 'lng': longitude, 'radius': radius, 'start': calendar.timegm(start.utctimetuple()), 'end': calendar.timegm(end.utctimetuple()) } }
		response['status'] = ProgressStatus.NEW
		# process the results and already preprocess them for clustering stage
		results = db.tweets.find(query).sort([('retweet_count', DESCENDING), ('favorite_count', DESCENDING)]).limit(SEARCH_QUERY_RESULT_LIMIT)

		response['clusters'] = []
		if results.count() > 0:
			logging.info('Query: %s retrieved %d documents.', query, results.count())

			response = create_cluster(cache_query_key, response, cluster, location_map)

			return jsonify(response)
		else:
			response['status'] = ProgressStatus.DONE
			return jsonify(response)
	except ValueError:
		abort(404)

if __name__ == '__main__':
	app.run(debug=True, host='0.0.0.0', port=5000) # TODO: make debug mode conditional depending on env or args
