import os
from flask import Flask, jsonify
from pymongo import MongoClient, GEO2D

addr = os.getenv('MONGO_PORT_27017_TCP_ADDR', 'localhost')
port = os.getenv('MONGO_PORT_27017_TCP_PORT', '27017')
client = MongoClient('mongodb://analysis:supertopsecret@' + addr + ':' + port + '/analysis')
db = client.analysis
db.clusters.ensure_index([("loc", GEO2D)])
# TODO: http://api.mongodb.com/python/current/examples/geo.html

app = Flask(__name__)

@app.route('/')
def index(): # default path to quickly curl/wget and test if running
	return 'Analysis REST-DB-Frontend running!'

@app.route('/analysis/v1.0/clusters', methods=['GET'])
def get_all_clusters():
	return jsonify({'Hello': 'World'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # TODO: make debug mode conditional depending on env or args
