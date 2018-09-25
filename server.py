from flask import Flask, abort, make_response, jsonify
import os
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt import JWT, jwt_required
from werkzeug.security import safe_str_cmp
from binascii import hexlify
import base64
from peewee import DoesNotExist
from lib import get_county_from_location, get_county_from_address
from lib.models import APIConsumer, County
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['JWT_AUTH_USERNAME_KEY'] = "api_key"
app.config['JWT_AUTH_PASSWORD_KEY'] = "api_secret"
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["2 per minute", "1 per second"],
)


def authenticate(api_key, api_secret):
    try:
        consumer = APIConsumer.get(api_key=api_key)
        if consumer and safe_str_cmp(consumer.api_secret.encode('utf-8'), api_secret.encode('utf-8')):
            return consumer
        return False
    except DoesNotExist:
        return False


def generate_keys():
    key = base64.b64encode(hexlify(os.urandom(24))).decode()
    secret = base64.b64encode(hexlify(os.urandom(32))).decode()
    return key, secret


def identity(payload):
    consumer_id = payload['identity']
    return APIConsumer.get(id=consumer_id)


jwt = JWT(app, authenticate, identity)


@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(jsonify(error="ratelimit exceeded %s" % e.description), 429)


@app.route('/county/<county_name>')
@jwt_required()
@limiter.limit(os.environ['REQUESTS_PER_MINUTE'] + " per minute")
def by_county(county_name):
    County.update_bans()
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="location is not in Texas"))


@app.route('/location/<lat>/<lng>')
@jwt_required()
@limiter.limit(os.environ['REQUESTS_PER_MINUTE'] + " per minute")
def by_location(lat, lng):
    County.update_bans()
    county_name = get_county_from_location(lat, lng)
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="Lat/Lng not found or location is not in Texas"))


@app.route('/place/<place>')
@jwt_required()
@limiter.limit(os.environ['REQUESTS_PER_MINUTE'] + " per minute")
def by_place(place):
    County.update_bans()
    county_name = get_county_from_address(place)
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="Address not found or location is not in Texas"))


if __name__ == '__main__':
    app.run(debug=False, port=os.environ['PORT'], host="0.0.0.0")
