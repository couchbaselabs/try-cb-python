from datetime import datetime
import math
import json
import uuid
from random import random
import jwt  # from PyJWT
import argparse
import requests

from flask import Flask, request, jsonify, abort, send_from_directory
from flask import make_response, redirect
from flask.views import View
from flask_classy import FlaskView, route

from couchbase.cluster import Cluster
from couchbase.cluster import ClusterOptions
from couchbase_core.cluster import PasswordAuthenticator
from couchbase.cluster import QueryOptions
from couchbase.search import MatchQuery, SearchOptions
import couchbase_core.subdocument as SD
import couchbase.search as FT
from couchbase.exceptions import *

# For Couchbase Server 5.0 there must be a username and password
# User must have full access to read/write bucket/data and
# Read access for Query and Search
# Cluster Administrator user may be used
# CONNSTR = 'couchbase://localhost/travel-sample?username=admin'
# PASSWORD = 'admin123'

DEFAULT_USER = "Administrator"
PASSWORD = 'password'

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--cluster', help='Connection String i.e. localhost')
parser.add_argument('-u', '--user', help='User with access to bucket')
parser.add_argument('-p', '--password', help='Password of user with access to bucket')
args = parser.parse_args()

if args.cluster:
        CONNSTR = "couchbase://" + args.cluster
else:
        CONNSTR = "couchbase://localhost"
if args.user and args.password:
    print((args.user, args.password))
    authenticator = PasswordAuthenticator(args.user, args.password)
else:
    authenticator = PasswordAuthenticator(DEFAULT_USER, PASSWORD)

print("Connecting to: " + CONNSTR)

app = Flask(__name__, static_url_path='/static')


@app.route('/')
def index():
    return redirect("/index.html", code=302)

@app.route('/<path:path>')
def serveFiles(path):
    return send_from_directory("static", path)

app.config.from_object(__name__)


def make_user_key(username):
    return 'user::' + username


class Airport(View):
    """Airport class for airport objects in the database"""

    def findall(self):
        """Returns list of matching airports and the source query"""

        querystr = request.args['search']
        #queryparams = request.args['search']
        queryprep = "SELECT airportname FROM `travel-sample` WHERE "
        sameCase = querystr == querystr.lower() or querystr == querystr.upper()
        if sameCase and len(querystr) == 3:
            queryprep += "faa = $1"
            queryargs = [querystr.upper()]
            #queryparams = querystr.upper()
        elif sameCase and len(querystr) == 4:
            queryprep += "icao = $1"
            queryargs = [querystr.upper()]
            #queryparams = querystr.upper()
        else:
            queryprep += "LOWER(airportname) LIKE $1"
            queryargs = [querystr.lower() + '%']
            #queryparams = querystr.lower()
        res = cluster.query(queryprep, *queryargs)
        # alternate in SDK3
        #res = cluster.query(queryprep, QueryOptions(positional_parameters=[queryparams]))
        #for row in res: print(res)
        airportslist = [x for x in res]
        context = [queryprep]
        #print (airportslist)
        response = make_response(jsonify({"data": airportslist, "context": context}))
        return response

    def dispatch_request(self):
        context = self.findall()
        return context


class FlightPathsView(FlaskView):
    """ FlightPath class for computed flights between two airports FAA codes"""

    @route('/<fromloc>/<toloc>', methods=['GET', 'OPTIONS'])
    def findall(self, fromloc, toloc):
        """
        Return flights information, cost and more for a given flight time
        and date
        """

        queryleave = convdate(request.args['leave'])
        queryprep = "SELECT faa as fromAirport,geo FROM `travel-sample` \
                    WHERE airportname = $1 \
                    UNION SELECT faa as toAirport,geo FROM `travel-sample` \
                    WHERE airportname = $2"
        res = cluster.query(queryprep, fromloc, toloc)
        flightpathlist = [x for x in res]
        context = [queryprep]

        # Extract the 'toAirport' and 'fromAirport' values.
        queryto = next(x['toAirport']
                       for x in flightpathlist if 'toAirport' in x)
        queryfrom = next(x['fromAirport']
                         for x in flightpathlist if 'fromAirport' in x)

        queryroutes = "SELECT a.name, s.flight, s.utc, r.sourceairport, r.destinationairport, r.equipment \
                        FROM `travel-sample` AS r \
                        UNNEST r.schedule AS s \
                        JOIN `travel-sample` AS a ON KEYS r.airlineid \
                        WHERE r.sourceairport = $1 AND r.destinationairport = $2 AND s.day = $3 \
                        ORDER BY a.name ASC;"

        # http://localhost:5000/api/flightpaths/Nome/Teller%20Airport?leave=01/01/2016
        # should produce query with OME, TLA faa codes
        resroutes = cluster.query(queryroutes, queryfrom, queryto, queryleave)
        routelist = []
        for x in resroutes:
            x['flighttime'] = math.ceil(random() * 8000)
            x['price'] = math.ceil(x['flighttime'] / 8 * 100) / 100
            routelist.append(x)
        response = make_response(jsonify({"data": routelist}))
        return response


class UserView(FlaskView):
    """Class for storing user related information and their carts"""

    @route('/login', methods=['POST', 'OPTIONS'])
    def login(self):
        """Login an existing user"""
        req = request.get_json()
        user = req['user'].lower()
        password = req['password']
        userdockey = make_user_key(user)

        try:
            doc_pass = db.lookup_in(userdockey, (
                SD.get('password'),
            )).content_as[str](0)
            
            if doc_pass != password:
                return abortmsg(401, "Password does not match")

        except SubdocPathNotFoundError:
            print("Password for user {} item does not exist".format(user))
        except NotFoundError:
            print("User {} item does not exist".format(user))
        except CouchbaseTransientError:
            print("Transient error received - has Couchbase stopped running?")
        except CouchbaseNetworkError:
            print("Network error received - is Couchbase Server running on this host?")
        else:
            return jsonify({'data': {'token': genToken(user)}})
        return abortmsg(500, "Failed to get user data")

    @route('/signup', methods=['POST', 'OPTIONS'])
    def signup(self):
        """Signup a new user"""
        req = request.get_json()
        user = req['user'].lower()
        userdockey = make_user_key(user)
        password = req['password']
        rawpassword = req['rawpassword']
        # Create sync gateway user
        try:
            headerInfo = {'Content-type': 'application/json', 'Accept': 'application/json'}
            sgUrl = "http://localhost:4985/travel-sample/_user/"
            sgValues = json.dumps({"name" : user, "password" : rawpassword})
            sgUser = requests.post(sgUrl, headers=headerInfo, data=sgValues)
            # print(sgValues)
        except Exception as e:
            print(e)
            return abortmsg(404, 'Please check that Sync Gateway is up and running')
        # Create user profile document in server bucket
        try:
            db.upsert(userdockey, {'username': user, 'password': password})
            respjson = jsonify({'data': {'token': genToken(user)}})
            response = make_response(respjson)
            return response
        except Exception as e:
            print(e)
            abort(409)

    @route('/<username>/flights', methods=['GET', 'POST', 'OPTIONS'])
    def userflights(self, username):
         user = username.lower()

         """List the flights that have been reserved by a user"""
         if request.method == 'GET':
            bearer = request.headers['Authorization']
            if not auth(bearer, user):
                return abortmsg(401, 'Username does not match token username')

            try:
                userdockey = make_user_key(user)
                rv = db.lookup_in(userdockey, (SD.get('flights'),))
                booked_flights = rv.content_as[list](0)
                print(booked_flights)
                respjson = jsonify({"data": booked_flights})
                response = make_response(respjson)
                return response

            except NotFoundError:
                return abortmsg(500, "User does not exist")

         # """Book a new flight for a user"""
         elif request.method == 'POST':

            bearer = request.headers['Authorization']
            if not auth(bearer, user):
                return abortmsg(401, 'Username does not match token username')

            newflight = request.get_json()['flights'][0]
            userdockey = make_user_key(user)

            try:
                db.mutate_in(userdockey, (SD.array_append('flights',
                                          newflight, create_parents=True),))
                resjson = {'data': {'added': newflight},
                           'context': 'Update document ' + userdockey}
                return make_response(jsonify(resjson))
            except NotFoundError:
                return abortmsg(500, "User does not exist")
            except CouchbaseDataError:
                return abortmsg(409, "Couldn't update flights")


class HotelView(FlaskView):
    """Class for storing Hotel search related information"""

    @route('/<description>/<location>/', methods=['GET'])
    def findall(self, description, location):
        """Find hotels using full text search"""
        # Requires FTS index called 'hotels'
        # TODO auto create index if missing
        qp = FT.ConjunctionQuery(FT.TermQuery(term='hotel', field='type'))
        if location != '*':
            qp.conjuncts.append(
                FT.DisjunctionQuery(
                    FT.MatchPhraseQuery(location, field='country'),
                    FT.MatchPhraseQuery(location, field='city'),
                    FT.MatchPhraseQuery(location, field='state'),
                    FT.MatchPhraseQuery(location, field='address')
                ))

        if description != '*':
            qp.conjuncts.append(
                FT.DisjunctionQuery(
                    FT.MatchPhraseQuery(description, field='description'),
                    FT.MatchPhraseQuery(description, field='name')
                ))

        q = cluster.search_query('hotels', qp, SearchOptions(limit=100))
        results = []

        cols = ['address','city', 'state', 'country', 'name','description','id']
        for row in q.rows():
            subdoc = db.lookup_in(row.id, tuple(SD.get(x) for x in cols))
            # Get the address fields from the document, if they exist
            addr = ', '.join(subdoc.content_as[str](c) for c in cols[:4]
                             if subdoc.content_as[str](c) != "None")
            subresults = dict((c, subdoc.content_as[str](c)) for c in cols)
            subresults['address'] = addr
            subresults['id'] = "hotel"+row.id
            results.append(subresults)


        response = {'data': results}
        return jsonify(response)


def abortmsg(code, message):
    response = jsonify({'message': message})
    response.status_code = code
    return response


def convdate(rawdate):
    """Returns integer data from mm/dd/YYYY"""
    day = datetime.strptime(rawdate, '%m/%d/%Y')
    return day.weekday()

JWT_SECRET = 'cbtravelsample'
def genToken(username):
    return jwt.encode({'user': username.lower()}, JWT_SECRET).decode("ascii")

def auth(bearerHeader, username):
    bearer = bearerHeader.split(" ")[1]
    return username == jwt.decode(bearer, JWT_SECRET)['user']


# Setup pluggable Flask views routing system
HotelView.register(app, route_prefix='/api/')
# Added route_base below to allow camelCase view name
FlightPathsView.register(app, route_prefix='/api/', route_base='flightPaths')
UserView.register(app, route_prefix='/api/')

app.add_url_rule('/api/airports', view_func=Airport.as_view('airports'),
                 methods=['GET', 'OPTIONS'])


def connect_db():
    print(CONNSTR, authenticator)
    cluster = Cluster(CONNSTR, ClusterOptions(authenticator))
    static_bucket = cluster.bucket('travel-sample')
    collection = static_bucket.default_collection()
    return collection

cluster = Cluster(CONNSTR, ClusterOptions(authenticator))
static_bucket = cluster.bucket('travel-sample')
db = connect_db()

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=8080)
