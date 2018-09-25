import requests, json, sys


r = requests.post("http://localhost:2222/auth", json={"api_key":sys.argv[1], "api_secret":sys.argv[2]})
at = r.json()['access_token']


r = requests.get("http://localhost:2222/county/travis", headers={"Authorization":"JWT %s" % at})
print(r.json())