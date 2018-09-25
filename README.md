# burnban
Simple API for querying TAMU burn ban information by county (Texas only) 
https://burnban.herokuapp.com

## Endpoints:

### POST /auth 
Post API key and secret to this endpoint to receive a JWT token. All other endpoints require a valid token. 
{ "api_key":"test_key", "api_secret":"test_secret"}

### GET /county/\<county_name\>
Returns current burn ban status for a given county

### GET /location/\<lat\>/\<lng\>
Returns current burn ban status for a particular location. Returns 404 if location is outside of Texas. Uses FCC Area API to determine county name from lat/lng

### GET /place/\<place\>

Returns current burn ban status for a particular address/place description. Uses Nominatum API to gecode the address and then uses FCC Area API to determine county name from lat/lng. Returns 404 if location is outside of Texas.



## Running the server
honcho/foreman/nf start

## Initialize the Database
honcho/foreman/nf run python3 tasks/init_db.py

## Generate API Key/Secret (also inserts into DB)
honcho/foreman/nf run python3 tasks/generate_keys.py
