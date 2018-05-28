import os
from flask import Flask
from flask import request
from flask import jsonify
from flask_api import FlaskAPI
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_jwt_extended import (JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt_claims)
from pymongo import MongoClient
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = FlaskAPI(__name__)
CORS(app)

MONGO_URL = os.environ.get('MONGO_URL')
if not MONGO_URL:
    MONGO_URL = 'mongodb://127.0.0.1:27017'

app.config['MONGO_URI'] = MONGO_URL
app.config['JWT_SECRET_KEY'] = 'super-secret'
mongo = PyMongo(app, config_prefix='MONGO')

DEVELOPER_KEY = 'AIzaSyBBkE1TxusqqxvF62mRcRXQEhtNSqYOXT4'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

# Setup the Flask-JWT-Extended extension
jwt = JWTManager(app)

@app.route('/')
def redirect():
    return 'Hello World'

@app.route('/v1/api/getJWTToken', methods=['GET'])
def verify_token():
    user = mongo.db.users.find({ 'email' : request.args.get('email') })
    if (user.count() == 0):
        # User doesn't exist, create and insert user into database
        mongo.db.users.insert({ 'email' : request.args.get('email'), 'token' : request.args.get('token') })

    # Create JWT Access Token and send back to client-side
    access_token = create_access_token(identity=request.args.get('email'))
    return jsonify(access_token=access_token), 200

@app.route('/v1/api/getStreamList', methods=['GET'])
def youtube_search():
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
        developerKey=DEVELOPER_KEY)

    searchTerm = request.args.get('searchValue')

    # Set the previous or next page token if available
    if request.args.get('pageToken') is None:
        pageToken = ''
    else:
        pageToken = request.args.get('pageToken')

    # Call the search.list method to retrieve results matching the specified query term.
    search_response = youtube.search().list(
        q=searchTerm,
        part='id,snippet',
        eventType='live',
        type='video',
        maxResults=20,
        pageToken=pageToken
    ).execute()

    videos = []

    # Append Title, Video ID, and Thumbnail data into videos array
    for search_result in search_response.get('items', []):
        videos.append({
            'title': search_result['snippet']['title'],
            'id': search_result['id']['videoId'],
            'thumbnail': search_result['snippet']['thumbnails']['high']
        })

    # Previous Page Token
    if 'prevPageToken' not in search_response:
        prevToken = ''
    else:
        prevToken = search_response['prevPageToken']

    # Next Page Token
    if 'nextPageToken' not in search_response:
        nextToken = ''
    else:
        nextToken = search_response['nextPageToken']

    response_data = {
        'nextPageToken': nextToken,
        'prevPageToken': prevToken,
        'pageInfo': search_response['pageInfo'],
        'videos': videos
    }

    return response_data

@app.after_request

def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

# Protect a view with jwt_required, which requires a valid access token in the request to access.
@app.route('/protected', methods=['GET'])
@jwt_required
def protected():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200

if __name__ == "__main__":
    app.run(debug=True)