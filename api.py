import os
from flask import Flask
from flask import request
from flask import jsonify
from flask_api import FlaskAPI
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_jwt_extended import (JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt_claims)
from pymongo import MongoClient

app = FlaskAPI(__name__)
CORS(app)

MONGO_URL = os.environ.get('MONGO_URL')
if not MONGO_URL:
    MONGO_URL = 'mongodb://127.0.0.1:27017'

app.config['MONGO_URI'] = MONGO_URL
app.config['JWT_SECRET_KEY'] = 'super-secret'
mongo = PyMongo(app, config_prefix='MONGO')

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

@app.route('/add')
def add():
    user = mongo.db.users
    user.remove({'name' : 'Brack Panther'})
    return 'User Added!'

@app.route('/user', methods=['GET', 'POST'])
def get_user():
    """
    Get User
    """
    if request.method == 'POST':
        return { 'request data' : request.data }

@app.after_request

def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == "__main__":
    app.run(debug=True)