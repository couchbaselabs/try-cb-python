import argparse
import math
import uuid
from datetime import datetime
from random import random

import couchbase.search as FT
import couchbase.subdocument as SD
import jwt  # from PyJWT
from couchbase.cluster import Cluster, ClusterOptions, PasswordAuthenticator
from couchbase.exceptions import *
from couchbase.search import SearchOptions
from flask import Flask, jsonify, make_response, request
from flask.blueprints import Blueprint
from flask_classy import FlaskView
from flask_cors import CORS, cross_origin

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
parser.add_argument('-p', '--password',
                    help='Password of user with access to bucket')
args = parser.parse_args()

if args.cluster:
    CONNSTR = "couchbase://" + args.cluster
else:
    # 'db' is an alias that resolves to the couchbase-server docker hostname.
    # See `docker-compose.yml (line 25)`.
    CONNSTR = "couchbase://db"
if args.user and args.password:
    print((args.user, args.password))
    authenticator = PasswordAuthenticator(args.user, args.password)
else:
    authenticator = PasswordAuthenticator(DEFAULT_USER, PASSWORD)

print("Connecting to: " + CONNSTR)

app = Flask(__name__)
app.config.from_object(__name__)
app.config['CORS_HEADERS'] = 'Content-Type'

api = Blueprint("api", __name__)

CORS(app, headers=['Content-Type', 'Authorization'])


@app.route('/')
def index():
    """Returns the list of api endpoints"""
    endpoints = [str(rule) for rule in app.url_map.iter_rules()]
    return jsonify(endpoints)


def make_user_key(username):
    return username.lower()


class AirportView(FlaskView):
    """Airport class for airport objects in the database"""

    @api.route('/airports', methods=['GET', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def airports():
        """Returns list of matching airports and the source query"""

        querytype = "N1QL query - scoped to inventory: "

        querystr = request.args['search']
        queryprep = "SELECT airportname FROM `travel-sample`.inventory.airport WHERE "
        sameCase = querystr == querystr.lower() or querystr == querystr.upper()
        if sameCase and len(querystr) == 3:
            queryprep += "faa=$1"
            queryargs = [querystr.upper()]
        elif sameCase and len(querystr) == 4:
            queryprep += "icao=$1"
            queryargs = [querystr.upper()]
        else:
            queryprep += "POSITION(LOWER(airportname), $1) = 0"
            queryargs = [querystr.lower()]

        res = cluster.query(queryprep, *queryargs)
        airportslist = [x for x in res]
        context = [querytype + queryprep]
        response = make_response(
            jsonify({"data": airportslist, "context": context}))
        return response


class FlightPathsView(FlaskView):
    """ FlightPath class for computed flights between two airports FAA codes"""

    @api.route('/flightPaths/<fromloc>/<toloc>', methods=['GET', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def flightPaths(fromloc, toloc):
        """
        Return flights information, cost and more for a given flight time
        and date
        """

        querytype = "N1QL query - scoped to inventory: "

        queryleave = convdate(request.args['leave'])
        queryprep = "SELECT faa as fromAirport FROM `travel-sample`.inventory.airport \
                    WHERE airportname = $1 \
                    UNION SELECT faa as toAirport FROM `travel-sample`.inventory.airport \
                    WHERE airportname = $2"
        res = cluster.query(queryprep, fromloc, toloc)
        flightpathlist = [x for x in res]
        context = [querytype + queryprep]

        # Extract the 'fromAirport' and 'toAirport' values.
        queryfrom = next(x['fromAirport']
                         for x in flightpathlist if 'fromAirport' in x)
        queryto = next(x['toAirport']
                       for x in flightpathlist if 'toAirport' in x)

        queryroutes = "SELECT a.name, s.flight, s.utc, r.sourceairport, r.destinationairport, r.equipment \
                        FROM `travel-sample`.inventory.route AS r \
                        UNNEST r.schedule AS s \
                        JOIN `travel-sample`.inventory.airline AS a ON KEYS r.airlineid \
                        WHERE r.sourceairport = $fromfaa AND r.destinationairport = $tofaa AND s.day = $dayofweek \
                        ORDER BY a.name ASC;"

        # http://localhost:8080/api/flightPaths/Nome/Teller%20Airport?leave=01/01/2016
        # should produce query with OME, TLA faa codes
        resroutes = cluster.query(
            queryroutes, fromfaa=queryfrom, tofaa=queryto, dayofweek=queryleave)
        routelist = []
        for x in resroutes:
            x['flighttime'] = math.ceil(random() * 8000)
            x['price'] = math.ceil(x['flighttime'] / 8 * 100) / 100
            routelist.append(x)

        # Include second query in context
        context.append(querytype + queryroutes)

        response = make_response(
            jsonify({"data": routelist, "context": context}))
        return response


class TenantUserView(FlaskView):
    """Class for storing user related information for a given tenant"""

    @api.route('/tenants/<tenant>/user/login', methods=['POST', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def login(tenant):
        """Login an existing user"""
        agent = make_user_key(tenant)
        req = request.get_json()
        user = make_user_key(req['user'])
        password = req['password']

        scope = bucket.scope(agent)
        users = scope.collection('users')

        querytype = "KV get - scoped to " + scope.name + \
            ".users" + ": for password field in document "
        try:
            doc_pass = users.lookup_in(user, (
                SD.get('password'),
            )).content_as[str](0)

            if doc_pass != password:
                return abortmsg(401, "Password does not match")

        except DocumentNotFoundException:
            print("User {} item does not exist".format(user))
        except CouchbaseTransientException:
            print("Transient error received - has Couchbase stopped running?")
        except NetworkException:
            print("Network error received - is Couchbase Server running on this host?")
        else:
            return jsonify({'data': {'token': genToken(user)}, 'context': querytype + user})

        return abortmsg(401, "Failed to get user data")

    @api.route('/tenants/<tenant>/user/signup', methods=['POST', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def signup(tenant):
        """Signup a new user"""
        agent = make_user_key(tenant)
        req = request.get_json()
        user = make_user_key(req['user'])
        password = req['password']

        scope = bucket.scope(agent)
        users = scope.collection('users')

        querytype = "KV insert - scoped to " + scope.name + \
            ".users" + ": document "
        try:
            users.insert(user, {'username': user, 'password': password})
            respjson = jsonify(
                {'data': {'token': genToken(user)}, 'context': querytype + user})
            response = make_response(respjson)
            return response

        except DocumentExistsException:
            print("User {} item already exists".format(user))
            return abortmsg(409, "User already exists")
        except Exception as e:
            print(e)
            return abortmsg(500, "Failed to save user")

    @api.route('/tenants/<tenant>/user/<username>/flights', methods=['GET', 'PUT', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def flights(tenant, username):
        agent = make_user_key(tenant)
        user = make_user_key(username)

        scope = bucket.scope(agent)
        users = scope.collection('users')
        flights = scope.collection('bookings')

        """List the flights that have been reserved by a user"""
        if request.method == 'GET':
            bearer = request.headers['Authorization']
            if not auth(bearer, user):
                return abortmsg(401, 'Username does not match token username')

            try:
                userdockey = make_user_key(username)
                rv = users.lookup_in(userdockey, (SD.get('bookings'),))
                booked_flights = rv.content_as[list](0)
                rows = []
                for key in booked_flights:
                    rows.append(flights.get(key).content_as[dict])
                print(rows)

                querytype = "KV get - scoped to " + scope.name + \
                    ".user" + ": for " + \
                    str(len(booked_flights)) + " bookings in document "
                respjson = jsonify({"data": rows, "context": querytype + user})
                response = make_response(respjson)
                return response

            except DocumentNotFoundException:
                return abortmsg(401, "User does not exist")

        # """Book a new flight for a user"""
        elif request.method == 'PUT':

            bearer = request.headers['Authorization']
            if not auth(bearer, user):
                return abortmsg(401, 'Username does not match token username')

            newflight = request.get_json()['flights'][0]
            flight_id = str(uuid.uuid4())

            try:
                flights.upsert(flight_id, newflight)
            except Exception as e:
                print(e)
                return abortmsg(500, "Failed to add flight data")

            try:
                users.mutate_in(user, (SD.array_append('bookings',
                                                       flight_id, create_parents=True),))

                querytype = "KV update - scoped to " + scope.name + \
                    ".user" + ": for bookings field in document "
                resjson = {'data': {'added': newflight},
                           'context': querytype + user}
                return make_response(jsonify(resjson))
            except DocumentNotFoundException:
                return abortmsg(401, "User does not exist")
            except Exception:
                return abortmsg(500, "Couldn't update flights")


class HotelView(FlaskView):
    """Class for storing Hotel search related information"""

    @api.route('/hotels/<description>/<location>/', methods=['GET'])
    @cross_origin(supports_credentials=True)
    def hotels(description, location):
        # Requires FTS index called 'hotels-index'
        # TODO auto create index if missing
        """Find hotels using full text search"""
        qp = FT.ConjunctionQuery()
        if location != '*' and location != "":
            qp.conjuncts.append(
                FT.DisjunctionQuery(
                    FT.MatchPhraseQuery(location, field='country'),
                    FT.MatchPhraseQuery(location, field='city'),
                    FT.MatchPhraseQuery(location, field='state'),
                    FT.MatchPhraseQuery(location, field='address')
                ))

        if description != '*' and description != "":
            qp.conjuncts.append(
                FT.DisjunctionQuery(
                    FT.MatchPhraseQuery(description, field='description'),
                    FT.MatchPhraseQuery(description, field='name')
                ))

        scope = bucket.scope('inventory')
        hotel_collection = scope.collection('hotel')
        q = cluster.search_query('hotels-index', qp, SearchOptions(limit=100))
        results = []
        cols = ['address', 'city', 'state', 'country', 'name', 'description']
        for row in q:
            subdoc = hotel_collection.lookup_in(
                row.id, tuple(SD.get(x) for x in cols))
            # Get the address fields from the document, if they exist
            addr = ', '.join(subdoc.content_as[str](c) for c in cols[:4]
                             if subdoc.content_as[str](c) != "None")
            subresults = dict((c, subdoc.content_as[str](c)) for c in cols[4:])
            subresults['address'] = addr
            results.append(subresults)

        querytype = "FTS search - scoped to: " + scope.name + \
            ".hotel" + " within fields " + ', '.join(cols)
        response = {'data': results, 'context': querytype}
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
    return jwt.encode({'user': make_user_key(username)}, JWT_SECRET, algorithm='HS256').decode("ascii")


def auth(bearerHeader, username):
    bearer = bearerHeader.split(" ")[1]
    return username == jwt.decode(bearer, JWT_SECRET)['user']


app.register_blueprint(api, url_prefix="/api")


def connect_db():
    print(CONNSTR, authenticator)
    cluster = Cluster(CONNSTR, ClusterOptions(authenticator))
    bucket = cluster.bucket('travel-sample')
    return cluster, bucket


cluster, bucket = connect_db()

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=8080, threaded=False)
