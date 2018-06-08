import os
import dateutil.parser
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
    MONGO_URL = 'mongodb://admin:pass123@ds141320.mlab.com:41320/live-feed-db'

app.config['MONGO_URI'] = MONGO_URL
app.config['JWT_SECRET_KEY'] = 'super-secret'
mongo = PyMongo(app, config_prefix='MONGO')

DEVELOPER_KEY = 'AIzaSyBBkE1TxusqqxvF62mRcRXQEhtNSqYOXT4'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

# Setup the Flask-JWT-Extended extension
jwt = JWTManager(app)

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
@jwt_required
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

@app.route('/v1/api/getStreamMessages', methods=['GET'])
@jwt_required
def stream_messages():
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
        developerKey=DEVELOPER_KEY)
    
    videoID = request.args.get('videoID')
    pageToken = request.args.get('pageToken')

    # Call the videos.list method to retrieve the liveChatID of the specified video.
    video_response = youtube.videos().list(
        part='id,snippet,liveStreamingDetails',
        id=videoID,
    ).execute()

    video = []

    for video_result in video_response.get('items', []):
        video.append({
            'title': video_result['snippet']['title'],
            'liveStreamID': video_result['liveStreamingDetails']
        })

    # Check if live chat ID exists
    if 'activeLiveChatId' not in video[0]['liveStreamID']:
        return []
    else:
        messages_response = youtube.liveChatMessages().list(
            liveChatId=video[0]['liveStreamID']['activeLiveChatId'],
            part='id,snippet,authorDetails',
            maxResults=200,
            pageToken=pageToken
        ).execute()

    for message_item in messages_response.get('items', []):
        existingMessage = mongo.db.messages.find({ 'id': message_item['id'] })

        # Skip existing messages to avoid saving duplicates
        if (existingMessage.count() == 0):
            # Save messages into database
            mongo.db.messages.insert({
                'id' : message_item['id'],
                'username' : message_item['authorDetails']['displayName'],
                'message' : message_item['snippet']['textMessageDetails']['messageText'],
                'published' : message_item['snippet']['publishedAt'],
            })

        date = dateutil.parser.parse(message_item['snippet']['publishedAt'])
        message_item['snippet']['publishedAt'] = date.ctime()

    return messages_response

@app.route('/v1/api/getMessages', methods=['GET'])
@jwt_required
def get_messages():
    searchTerm = request.args.get('searchValue')
    messages = []

    # Sort results by date/time published in ascending order
    userMessages = mongo.db.messages.find({ 'username' : searchTerm }).sort('published', 1)

    for message in userMessages:
        # Format time
        date = dateutil.parser.parse(message['published'])

        messages.append({
            'username': message['username'],
            'message': message['message'],
            'published': date.ctime()
        })

    return messages

@app.after_request

def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == "__main__":
    app.run(debug=True)