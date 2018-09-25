# burnban
Simple API for querying TAMU burn ban information by county (Texas only)

## Endpoints:

### GET /county/\<county_name\>
Returns current burn ban status for a given county

### GET /location/\<lat\>/\<lng\>
Returns current burn ban status for a particular location. Returns 404 if location is outside of Texas. Uses FCC Area API to determine county name from lat/lng

### GET /place/\<place\>

Returns current burn ban status for a particular address/place description. Uses Nominatum API to gecode the address and then uses FCC Area API to determine county name from lat/lng. Returns 404 if location is outside of Texas.
