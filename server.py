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

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["2 per minute", "1 per second"],
)

db = connect(os.environ['DATABASE_URL'])


def get_banned_counties():
    r = requests.get(os.environ['BURNBAN_URL'])
    e = xml.etree.ElementTree.fromstring(r.content)
    counties = ([i.strip() for i in e.find('channel').find('item').find('description').text.split(',')])
    logging.debug(counties)
    return counties


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
        if cls._get_earliest_update() < (datetime.datetime.utcnow() - datetime.timedelta(seconds=1)):
            counties = get_banned_counties()
            with cls._meta.database.atomic():
                cls.update(burn_ban=False, updated_date=datetime.datetime.utcnow()).execute()
                cls.update(burn_ban=True, updated_date=datetime.datetime.utcnow()).where(County.name << counties).execute()


def get_county_from_location(lat, lng):
    r = requests.get(os.environ['FCC_URL'], params={"lat": lat, "lon": lng, "format": "json"})
    return r.json()['results'][0]['county_name'].upper()


def get_county_from_address(query):
    r = requests.get(os.environ['NOMINATUM_URL'], params={"q": query, "format": "json"}).json()[0]
    return get_county_from_location(r['lat'], r['lon'])


@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(jsonify(error="ratelimit exceeded %s" % e.description), 429)


@app.route('/county/<county_name>')
@limiter.limit("1 per minute")
def by_county(county_name):
    County.update_bans()
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="location is not in Texas"))


@app.route('/location/<lat>/<lng>')
@limiter.limit("10 per minute")
def by_location(lat, lng):
    County.update_bans()
    county_name = get_county_from_location(lat, lng)
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(jsonify(error="Lat/Lng not found or location is not in Texas"))


@app.route('/place/<place>')
@limiter.limit("10 per minute")
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
        db.create_tables([County])
        sql_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'initialize.sql')
        with open(sql_path, 'r') as sql_file:
            db.execute_sql(sql_file.read())
