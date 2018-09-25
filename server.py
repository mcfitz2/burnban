from flask import Flask, abort, make_response, jsonify
import requests
import json
import sys
import datetime
import os
import xml.etree.ElementTree
from peewee import fn, Model, DateTimeField, BooleanField, CharField, DoesNotExist
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt import JWT, jwt_required, current_identity
from werkzeug.security import safe_str_cmp
from binascii import hexlify
import base64

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret'
app.config['JWT_AUTH_USERNAME_KEY'] = "api_key"
app.config['JWT_AUTH_PASSWORD_KEY'] = "api_secret"
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["2 per minute", "1 per second"],
)

db = connect(os.environ['DATABASE_URL'])

class BaseModel(Model):
    class Meta:
        database = db

    def to_json(self):
        d = {k: v.isoformat() if isinstance(v, datetime.datetime) else v for k, v in model_to_dict(self).items() if k != "id"}
        return json.dumps(d)


class County(BaseModel):
    name = CharField(unique=True)
    burn_ban = BooleanField()
    updated_date = DateTimeField(null=True)

    @classmethod
    def _get_earliest_update(cls):
        return cls.select(fn.Min(cls.updated_date)).scalar()

    @classmethod
    def update_bans(cls):
        last_update = cls._get_earliest_update() 

        if (not last_update) or last_update < (datetime.datetime.utcnow() - datetime.timedelta(seconds=1)):
            counties = get_banned_counties()
            with cls._meta.database.atomic():
                cls.update(burn_ban=False, updated_date=datetime.datetime.utcnow()).execute()
                cls.update(burn_ban=True, updated_date=datetime.datetime.utcnow()).where(County.name << counties).execute()
class APIConsumer(BaseModel):
    api_key = CharField(unique=True)
    api_secret = CharField(unique=True)


def get_county_from_location(lat, lng):
    r = requests.get(os.environ['FCC_URL'], params={"lat": lat, "lon": lng, "format": "json"})
    return r.json()['results'][0]['county_name'].upper()


def get_county_from_address(query):
    r = requests.get(os.environ['NOMINATUM_URL'], params={"q": query, "format": "json"}).json()[0]
    return get_county_from_location(r['lat'], r['lon'])

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

def get_banned_counties():
    r = requests.get(os.environ['BURNBAN_URL'])
    e = xml.etree.ElementTree.fromstring(r.content)
    counties = ([i.strip() for i in e.find('channel').find('item').find('description').text.split(',')])
    logging.debug(counties)
    return counties

jwt = JWT(app, authenticate, identity)



@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(jsonify(error="ratelimit exceeded %s" % e.description), 429)


@app.route('/county/<county_name>')
@jwt_required()
@limiter.limit(os.environ['REQUESTS_PER_MINUTE']+" per minute")
def by_county(county_name):
    County.update_bans()
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="location is not in Texas"))


@app.route('/location/<lat>/<lng>')
@jwt_required()
@limiter.limit(os.environ['REQUESTS_PER_MINUTE']+" per minute")
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
@limiter.limit(os.environ['REQUESTS_PER_MINUTE']+" per minute")
def by_place(place):
    County.update_bans()
    county_name = get_county_from_address(place)
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="Address not found or location is not in Texas"))


if __name__ == '__main__':
    command = sys.argv[1]
    if command == "run":
            app.run(debug=False, port=os.environ['PORT'], host="0.0.0.0")
    elif command == "init":
        db.execute_sql("DROP TABLE county CASCADE;")
        db.execute_sql("DROP TABLE apiconsumer CASCADE;")
        db.create_tables([County, APIConsumer])
        db.execute_sql("insert into apiconsumer (api_key, api_secret) values ('test', 'test2')")
        sql_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'initialize.sql')
        with open(sql_path, 'r') as sql_file:
            db.execute_sql(sql_file.read())
    elif command == "generate":
        key, secret = generate_keys()
        a = APIConsumer.create(api_key=key, api_secret=secret)
        a.save()
        print("Key: %s" % key)
        print("Secret: %s" % secret)