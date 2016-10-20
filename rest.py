import os
import time
from flask import Flask, jsonify
from pymongo import MongoClient, GEO2D

def connect_to_and_setup_database():
	addr = os.getenv('MONGODB_PORT_27017_TCP_ADDR', 'localhost')
	port = os.getenv('MONGODB_PORT_27017_TCP_PORT', '27017')
	passwd = os.getenv('MONGODB_PASS', 'supertopsecret')
	client = MongoClient('mongodb://analysis:' + passwd + '@' + addr + ':' + port + '/analysis')
	db = client.analysis
	db.clusters.ensure_index([("loc", GEO2D)])
	# TODO: http://api.mongodb.com/python/current/examples/geo.html
	return client, db

connected = False
while not connected:
	try:
		client, db = connect_to_and_setup_database()
		connected = True
	except Exception as error: 
		print('DATABASE SETUP ERROR: ' + repr(error))
		time.sleep(2) # wait with the retry


app = Flask(__name__)

@app.route('/')
def index(): # default path to quickly curl/wget and test if running
	return 'Analysis REST-DB-Frontend running!'

@app.route('/analysis/v1.0/clusters', methods=['GET'])
def get_all_clusters():
	return jsonify({'Hello': 'World'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # TODO: make debug mode conditional depending on env or args
