from datetime import timedelta

# needed for any cluster connection
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
# needed for options -- cluster, timeout, SQL++ (N1QL) query, etc.
from couchbase.options import (ClusterOptions, ClusterTimeoutOptions)
from couchbase.exceptions import CouchbaseException
from couchbase.options import SearchOptions

from couchbase.search import QueryStringQuery, SearchOptions

# Update this to your cluster
# endpoint = < your capella instance Wide Area Network >
# username = <your database credentials username value>
# password = <your database crednentials password value >
bucket_name = "travel-sample"
# User Input ends here.

# Connect options - authentication
auth = PasswordAuthenticator(username, password)

# Connect options - global timeout opts
timeout_opts = ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))

# get a reference to our cluster
cluster = Cluster('couchbases://{}'.format(endpoint),
                  ClusterOptions(auth, timeout_options=timeout_opts))

# Wait until the cluster is ready for use.
cluster.wait_until_ready(timedelta(seconds=5))

# get a reference to our bucket
cb = cluster.bucket(bucket_name)

cb_coll = cb.scope("inventory").collection("airport")

# json object to be used in example update_airport_name function
updated_airport_name = {
        "airportname": "Heathrow Airport",
        "city": "London",
        "country": "United Kingdom",
        "faa": "LHR",
        "geo": {
            "alt": 83,
            "lat": 51.4775,
            "lon": -0.461389
        },
        "icao": "EGLL",
        "id": 507,
        "type": "airport",
        "tz": "Europe/London"
    }

# searches all airports
def get_all_airports():
    print("\nLookup Result: ")
    try:
        sql_query = 'SELECT * FROM `travel-sample`.inventory.airport'
        row_iter = cluster.query(
            sql_query,)
        for row in row_iter:
            print(row['airport']['airportname'])
    except Exception as e:
        print(e)

# updates airport
def update_airport_name(doc):
    print("\nUpsert CAS: ")
    try:
        # key will equal: "airport_507"
        key = doc["type"] + "_" + str(doc["id"])
        result = cb_coll.upsert(key, doc)
        print(result.cas)
    except Exception as e:
        print(e)

# searching a string with created FTS index called "Example"
def search_airport_inventory(search_string):
    try:
        result = cluster.search_query("Example", QueryStringQuery(search_string), SearchOptions(limit=10))
        for row in result.rows():
            print("Found row: {}".format(row))
    except CouchbaseException as e:
        print("Couchbase Error:"+str(e))
    except Exception as ex:
        print("Error:"+str(ex))
    

# uncomment each and run file to see output

# search_airport_inventory("Heathrow")

# get_all_airports()

# update_airport_name(updated_airport_name)

