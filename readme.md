# API

The REST-Service currently support radius search queries, e.g. for a local setup

```
curl -i http://127.0.0.1:5000/analysis/v1.0/search/0.0/0.0/3.0/1331856000.2/2000000000.2
```

With placeholder parameters the query looks like this:

```
/analysis/v1.0/search/<latitude>/<longitude>/<radius>/<tstart>/<tend>
```

* `latitude` and `longitude` are two floats describing the center position of the search query
* `radius` is simply the search radius
* `tstart` and `tend` are the start and end points of the timespan to be analyzed (expects UTC timestamps)
* all parameters are non-optional

# Response

The Server answers with a `404` error if the request is faulty in any way.
If a proper request was queried, the resulting data is process and JSON-Structure 
is returned, which contains an array of found clusters with words and their connected
words, the polarities of the words, and the word popularity. To verify the request
and proper time conversion a `query` object is attached to the response as well:

```
{
  "clusters": [
    {
      "connections": {
        "someword": {
          "other": 26, 
          "words": 28, 
          "and": 26, 
          "their": 27, 
          "connection": 27, 
          "strength": 81
        }, 
        ...
      }, 
      "polarities": {
        "someword": -0.7450549450549447, 
        "other": 0.8000000000000002, 
        "words": -0.9066666666666666,
        ...
      }, 
      "words": {
        "someword": 31, 
        "other": 139, 
        "words": 28, 
        ...
      }
    }, 
    ...
  ], 
  "query": {
    "end": 2000000000, 
    "lat": 0.0, 
    "lng": 0.0, 
    "radius": 3.0, 
    "start": 1331856000
  }
}
```

# JavaScript Query Example

An _untested_ JavaScript request would look roughly like this. An important detail is, that
JavaScript timestamps are in milliseconds therefore division is necessary. As far as I know 
JS-timstamps are already in UTC, so no special conversion for timezones should be necessary.

```
function getClusterData(lat, lng, radius, tstart, tend, callback)
{
	var url = "/analysis/v1.0/search/" + lat + "/" + lng + "/" + radius + "/" + Math.round(+tstart/1000) + "/" + Math.round(+tend/1000);
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState == 4 && xmlHttp.status == 200)
            callback(JSON.parse(xmlHttp.responseText));
    }
    xmlHttp.open("GET", url, true); 
    xmlHttp.send(null);
}
```