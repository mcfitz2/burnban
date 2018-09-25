from flask import Flask, abort
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
logging.basicConfig(level=logging.DEBUG)


app = Flask(__name__)
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


@app.route('/county/<county_name>')
def by_county(county_name):
    County.update_bans()
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(404)


@app.route('/location/<lat>/<lng>')
def by_location(lat, lng):
    County.update_bans()
    county_name = get_county_from_location(lat, lng)
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(404)


@app.route('/place/<place>')
def by_place(place):
    County.update_bans()
    county_name = get_county_from_address(place)
    try:
        county = County.get(name=county_name.upper())
        return county.to_json()
    except DoesNotExist:
        return abort(404)


if __name__ == '__main__':
    command = sys.argv[1]
    if command == "run":
            app.run(debug=True, port=os.environ['PORT'], host="0.0.0.0")
    elif command == "init":
        db.execute_sql("DROP TABLE county CASCADE;")
        db.create_tables([County])
        sql_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'initialize.sql')
        with open(sql_path, 'r') as sql_file:
            db.execute_sql(sql_file.read())
