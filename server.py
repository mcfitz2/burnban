from flask import Flask, request, abort
import requests, json
import datetime, os
import xml.etree.ElementTree
from dateutil.parser import parse
from json import JSONDecoder
from json import JSONEncoder

app = Flask(__name__)
data = None



class DateTimeDecoder(json.JSONDecoder):

    def __init__(self, *args, **kargs):
        JSONDecoder.__init__(self, object_hook=self.dict_to_object,*args, **kargs)
    def dict_to_object(self, d): 
        if '__type__' not in d:
            return d
        type = d.pop('__type__')
        try:
            dateobj = datetime.datetime(**d)
            return dateobj
        except Exception as e:
            print(e)
            d['__type__'] = type
            return d

class DateTimeEncoder(JSONEncoder):
    """ Instead of letting the default encoder convert datetime to string,
        convert datetime objects into a dict, which can be decoded by the
        DateTimeDecoder
    """

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return {
                '__type__' : 'datetime',
                'year' : obj.year,
                'month' : obj.month,
                'day' : obj.day,
                'hour' : obj.hour,
                'minute' : obj.minute,
                'second' : obj.second,
                'microsecond' : obj.microsecond,
            }
        else:
            return JSONEncoder.default(self, obj)

with open('data.json') as f:
	data = json.load(f, cls=DateTimeDecoder)
print(data['updated_date'])
def update_bans():
	if not 'updated_date' in data.keys() or not data['updated_date'] or (data['updated_date'] < datetime.datetime.now()-datetime.timedelta(hours=24)):
		r = requests.get('http://tfsfrp.tamu.edu/WILDFIRES/BURNBAN.XML')
		e = xml.etree.ElementTree.fromstring(r.content)
		counties = ([i.strip() for i in e.find('channel').find('item').find('description').text.split(',')])
		data['updated_date'] = datetime.datetime.now()
		for county_name, county in data['counties'].items():
			if county_name in counties:
				data['counties'][county_name.upper()]['burn_ban'] = True
			else:
				data['counties'][county_name.upper()]['burn_ban'] = False
		with open('data.json', 'w') as f:
			json.dump(data, f, cls=DateTimeEncoder)

update_bans()

def get_county(lat, lng):
	r = requests.get("https://geo.fcc.gov/api/census/area", params={"lat":lat, "lon":lng, "format":"json"})
	return r.json()['results'][0]['county_name'].upper()

@app.route('/county/<county>')
def by_county(county):
	update_bans()
	if county in data["counties"]:
		return json.dumps({"burn_ban":data["counties"][county.upper()]["burn_ban"], "updated_date":data["updated_date"].isoformat()}, cls=DateTimeEncoder)
	else:
		return abort(404)
@app.route('/location/<lat>/<lng>')
def by_location(lat, lng):
	update_bans()
	county = get_county(lat, lng)
	return json.dumps({"burn_ban":data["counties"][county.upper()]["burn_ban"], "updated_date":data["updated_date"].isoformat()}, cls=DateTimeEncoder)

@app.route('/place/<place>')
def by_place(place):
	update_bans()


if __name__ == '__main__':
    app.run(debug=True, port=os.environ['PORT'], host="0.0.0.0")
