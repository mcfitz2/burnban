import requests
import xml
import os
import logging


def get_county_from_location(lat, lng):
    r = requests.get(os.environ['FCC_URL'], params={"lat": lat, "lon": lng, "format": "json"})
    return r.json()['results'][0]['county_name'].upper()


def get_county_from_address(query):
    r = requests.get(os.environ['NOMINATUM_URL'], params={"q": query, "format": "json"}).json()[0]
    return get_county_from_location(r['lat'], r['lon'])


def get_banned_counties():
    r = requests.get(os.environ['BURNBAN_URL'])
    e = xml.etree.ElementTree.fromstring(r.content)
    counties = ([i.strip() for i in e.find('channel').find('item').find('description').text.split(',')])
    logging.debug(counties)
    return counties
