import argparse
import math
import uuid
import jwt  # from PyJWT
from datetime import datetime
from random import random
from flasgger import Swagger, SwaggerView
from flask import Flask, jsonify, make_response, request
from flask.blueprints import Blueprint
from flask_classy import FlaskView
from flask_cors import CORS, cross_origin

# Couchbase Imports
import couchbase.search as FT
import couchbase.subdocument as SD
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, SearchOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import *

# From Couchbase Server 5.0 onward, there must be a username and password.
# User must have full access to read/write bucket/data and read access for
# Query and Search.
# The default username and password are set in `wait-for-couchbase.sh`
# -----------LOCAL-----------
# CONNSTR = 'couchbase://db'
# USERNAME = 'Administrator'
# PASSWORD = 'password'
# ----------CAPELLA----------
# CONNSTR = 'couchbases://db'
# USERNAME = 'cbdemo'
# PASSWORD = 'Password123!'
# ---------------------------

# Editing this file? Replicate your changes in the 'sample-app.py' file in
# the 'docs-sdk-python' repo to have these changes appear in the tutorial.

JWT_SECRET = 'cbtravelsample'

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--cluster', help='Connection String i.e. localhost', default='db')
parser.add_argument('-s', '--scheme', help='couchbase or couchbases', default='couchbase')
parser.add_argument('-a', '--connectargs', help="?any_additional_args", default="")
parser.add_argument('-u', '--user', help='User with access to bucket')
parser.add_argument('-p', '--password', help='Password of user with access to bucket')

args = parser.parse_args()

# Init CB connection parameters

if not args.cluster:
  raise ConnectionError("No value for CB_HOST set!")
if not args.user:
    raise ConnectionError("No value for CB_USER set!")
if not args.password:
    raise ConnectionError("No value for CB_PSWD set!")

if ("couchbases://" in args.cluster) or ("couchbase://" in args.cluster):
	CONNSTR = f"{args.cluster}{args.connectargs}"
else:
	CONNSTR = f"{args.scheme}://{args.cluster}{args.connectargs}"
        
authenticator = PasswordAuthenticator(args.user, args.password)
print("Connecting to: " + CONNSTR)

# Initialise the web app
app = Flask(__name__)
app.config.from_object(__name__)
app.config['SWAGGER'] = {
    'openapi': '3.0.3',
    'title': 'Travel Sample API',
    'version': '1.0',
    'description': 'A sample API for getting started with Couchbase Server and the SDK.',
    'termsOfService': ''
}

swagger_template = {
    "components": {
        "securitySchemes": {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT Authorization header using the Bearer scheme."
            }
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "example": "An error message"
                    }
                }
            },
            "Context": {
                "type": "array",
                "items": {"type": "string"}
            },
            "ResultList": {
                "type": "object",
                "properties": {
                    "context": {"$ref": "#/components/schemas/Context"},
                    "data": {
                        "type": "array",
                        "items": {"type": "object"}
                    }
                }
            },
            "ResultSingleton": {
                "type": "object",
                "properties": {
                    "context": {"$ref": "#/components/schemas/Context"},
                    "data": {
                        "type": "object",
                    }
                }
            }
        }
    }
}


api = Blueprint("api", __name__)

CORS(app, headers=['Content-Type', 'Authorization'])

# The default API endpoint
@app.route('/')
def index():
    """Returns the index page
    ---
    responses:
        200:
          description: Returns the API index page
          content:
            text/html:
              example: <h1> Travel Sample API </h1>
    """

    return """
    <h1> Python Travel Sample API </h1>
    A sample API for getting started with Couchbase Server and the Python SDK.
    <ul>
    <li> <a href = "/apidocs"> Learn the API with Swagger, interactively </a>
    <li> <a href = "https://github.com/couchbaselabs/try-cb-python"> GitHub </a>
    </ul>
    """


def lowercase(key):
    return key.lower()

class AirportView(SwaggerView):
    """Airport class for airport objects in the database"""

    @api.route('/airports', methods=['GET', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def airports():
        """Returns list of matching airports and the source query
        ---
        tags:
        - airports
        parameters:
            - name: search
              in: query
              required: true
              schema:
                type: string
              example: SFO
              description: The airport name/code to search for
        responses:
            200:
              description: Returns airport data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultList' 
                  example:
                    context: ["A description of a SQL++ operation"]
                    data: [{"airportname": "San Francisco Intl"}]
        """

        queryType = "SQL++ query - scoped to inventory: "
        partialAirportName = request.args['search']

        queryPrep = "SELECT airportname FROM `travel-sample`.inventory.airport WHERE "
        sameCase = partialAirportName == partialAirportName.lower() or partialAirportName == partialAirportName.upper() #bool

        # The code does some guesswork to determine what the user is typing in.
        # This is based on string length and capitalization. If it believes the
        # string is an FAA or ICAO code, it queries for a match in the 'faa' or
        # 'icao' field. Otherwise, the code assumes a partial airport name, and
        # queries for a substring match at the start of the 'airportname' field

        if sameCase and len(partialAirportName) == 3:
            queryPrep += "faa=$1"
            queryArgs = [partialAirportName.upper()]
        elif sameCase and len(partialAirportName) == 4:
            queryPrep += "icao=$1"
            queryArgs = [partialAirportName.upper()]
        else:
            queryPrep += "POSITION(LOWER(airportname), $1) = 0"
            queryArgs = [partialAirportName.lower()]

        results = cluster.query(queryPrep, *queryArgs)
        airports = [x for x in results]

        # 'context' is returned to the frontend to be shown in the Query Log

        context = [queryType + queryPrep]

        response = make_response(jsonify({"data": airports, "context": context}))
        return response


class FlightPathsView(SwaggerView):
    """ FlightPath class for computed flights between two airports FAA codes"""

    @api.route('/flightPaths/<fromLoc>/<toLoc>', methods=['GET', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def flightPaths(fromLoc, toLoc):
        """
        Return flights information, cost and more for a given flight time and date
        ---
        tags:
        - flightPaths
        parameters:
            - name: fromLoc
              in: path
              required: true
              schema:
                type: string
              example: San Francisco Intl
              description: Airport name for beginning route
            - name: toLoc
              in: path
              required: true
              schema:
                type: string
              example: Los Angeles Intl
              description: Airport name for end route
            - name: leave
              in: query
              required: true
              schema:
                type: string
                format: date
              example: "05/24/2021"
              description: Date of flight departure in `mm/dd/yyyy` format
        responses:
            200:
              description: Returns flight data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultList'
                  example:
                    context: ["SQL++ query - scoped to inventory: SELECT faa as fromAirport FROM `travel-sample`.inventory.airport
                    WHERE airportname = $1 UNION SELECT faa as toAirport FROM `travel-sample`.inventory.airport WHERE airportname = $2"]
                    data: [{
                              "destinationairport": "LAX",
                              "equipment": "738",
                              "flight": "AA331",
                              "flighttime": 1220,
                              "name": "American Airlines",
                              "price": 152.5,
                              "sourceairport": "SFO",
                              "utc": "16:37:00"
                         }]
        """

        # 'context' is returned to the frontend to be shown in the Query Log

        queryType = "SQL++ query - scoped to inventory: "
        context = []

        faaQueryPrep = "SELECT faa as fromAirport FROM `travel-sample`.inventory.airport \
                        WHERE airportname = $1 \
                        UNION SELECT faa as toAirport FROM `travel-sample`.inventory.airport \
                        WHERE airportname = $2"
        
        faaResults = cluster.query(faaQueryPrep, fromLoc, toLoc)

        # The query results are an iterable object consisting of dicts with the
        # fields from each doc. The results from the query will be formatted as
        # [{'fromAirport':<faa code>}, {'toAirport':<faa code>}]
        # Note, results are unordered, so the ordering above may be inaccurate.
        # The iterable therefore needs to be flattened so the correct field can
        # be extracted.
        
        flightPathDict = {}
        for result in faaResults:
            flightPathDict.update(result)

        # flightPathDict will be formatted as
        # {'fromAirport':<faa code>, 'toAirport':<faa code>}

        queryFrom = flightPathDict['fromAirport']
        queryTo = flightPathDict['toAirport']

        context.append(queryType + faaQueryPrep)

        routeQueryPrep = "SELECT a.name, s.flight, s.utc, r.sourceairport, r.destinationairport, r.equipment \
                        FROM `travel-sample`.inventory.route AS r \
                        UNNEST r.schedule AS s \
                        JOIN `travel-sample`.inventory.airline AS a ON KEYS r.airlineid \
                        WHERE r.sourceairport = $fromfaa AND r.destinationairport = $tofaa AND s.day = $dayofweek \
                        ORDER BY a.name ASC;"

        # The date provided by the frontend needs to be converted into a number
        # between 0 and 6 (representing the days of the week) in order to match
        # the format in the database.

        flightDay = convdate(request.args['leave'])
        routeResults = cluster.query(routeQueryPrep, 
                                     fromfaa=queryFrom, 
                                     tofaa=queryTo, 
                                     dayofweek=flightDay)

        # The 'QueryResult' object can only be iterated over once - any further
        # attempts to do so will result in an 'AlreadyQueried' exception. It is
        # good practice to move the results into another data structure such as
        # a list.
        # Price data is not a part of the sample dataset, so a random number is
        # picked and added to the result dict.

        routesList = []
        for route in routeResults:
            route['price'] = math.ceil(random() * 500) + 250
            routesList.append(route)

        # Include the second routes query in the context
        context.append(queryType + routeQueryPrep)

        response = make_response(jsonify({"data": routesList, "context": context}))
        return response


class TenantUserView(SwaggerView):
    """Class for storing user related information for a given tenant"""

    @api.route('/tenants/<tenant>/user/login', methods=['POST', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def login(tenant):
        """Login an existing user for a given tenant agent
        ---
        tags:
        - tenants
        parameters:
            - name: tenant
              in: path
              required: true
              schema:
                type: string
              example: tenant_agent_00
              description: Tenant agent name
        requestBody:
            content:
              application/json:
                schema:
                  type: object
                  required:
                   - user
                   - password
                  properties:
                    user:
                      type: string
                      example: "user1"
                    password:
                      type: string
                      example: "password1"
        responses:
            200:
              description: Returns login data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultSingleton' 
                  example:
                    context: ["KV get - scoped to tenant_agent_00.users: for password field in document user1"]
                    data: 
                      token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoibXNfdXNlciJ9.GPs8two_vPVBpdqD7cz_yJ4X6J9yDTi6g7r9eWyAwEM
            401:
              description: Returns an authentication error
              content:
                application/json:
                    schema: 
                      $ref: '#/components/schemas/Error'
        """ 

        requestBody = request.get_json()
        user = requestBody['user']
        providedPassword = requestBody['password']

        userDocumentKey = lowercase(user)

        agent = lowercase(tenant)
        scope = bucket.scope(agent)
        users = scope.collection('users')

        queryType = f"KV get - scoped to {scope.name}.users: for password field in document "

        # Perform a sub-document GET request for the 'password' field on a
        # document with the provided username as the key.
        try:
            documentPassword = users.lookup_in(userDocumentKey, (
                SD.get('password'),
            )).content_as[str](0)

            if documentPassword != providedPassword:
                return abortmsg(401, "Password does not match")

        except DocumentNotFoundException:
            print(f"User {user} item does not exist", flush=True)
        except AmbiguousTimeoutException or UnAmbiguousTimeoutException:
            print("Request timed out - has Couchbase stopped running?", flush=True)
        else:
            return jsonify({'data': {'token': genToken(user)}, 'context': [queryType + user]})

        return abortmsg(401, "Failed to get user data")

    @api.route('/tenants/<tenant>/user/signup', methods=['POST', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def signup(tenant):
        """Signup a new user
        ---
        tags:
        - tenants
        parameters:
            - name: tenant
              in: path
              required: true
              schema:
                type: string
              example: tenant_agent_00
              description: Tenant agent name
        requestBody:
            content:
              application/json:
                schema:
                  type: object
                  required:
                   - user
                   - password
                  properties:
                    user:
                      type: string
                      example: "user1"
                    password:
                      type: string
                      example: "password1"
        responses:
            201:
              description: Returns login data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultSingleton' 
                  example:
                    context: ["KV insert - scoped to tenant_agent_00.users: document user1"]
                    data:
                      token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoibXNfdXNlciJ9.GPs8two_vPVBpdqD7cz_yJ4X6J9yDTi6g7r9eWyAwEM
            409:
              description: Returns a conflict error
              content:
                application/json:
                    schema: 
                      $ref: '#/components/schemas/Error'
        """
        
        requestBody = request.get_json()
        user = requestBody['user']
        password = requestBody['password']

        userDocumentKey = lowercase(user)

        agent = lowercase(tenant)
        scope = bucket.scope(agent)
        users = scope.collection('users')

        queryType = f"KV insert - scoped to {scope.name}.users: document "

        try:
            users.insert(userDocumentKey, {'username': user, 'password': password})
            responseJSON = jsonify(
                {'data': {'token': genToken(user)}, 'context': [queryType + user]})
            response = make_response(responseJSON)
            return response, 201

        except DocumentExistsException:
            print(f"User {user} item already exists", flush=True)
            return abortmsg(409, "User already exists")
        except Exception as e:
            print(e)
            return abortmsg(500, "Failed to save user", flush=True)

    @api.route('/tenants/<tenant>/user/<username>/flights', methods=['GET', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def getflights(tenant, username):
        """List the flights that have been reserved by a user
        ---
        tags:
        - tenants
        parameters:
            - name: tenant
              in: path
              required: true
              schema:
                type: string
              example: tenant_agent_00
              description: Tenant agent name
            - name: username
              in: path
              required: true
              schema:
                type: string
              example: user1
              description: Username
        responses:
            200:
              description: Returns flight data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultList'
                  example: 
                      context: ["KV get - scoped to tenant_agent_00.users: for 2 bookings in document user1"]
                      data: [
                              {
                                "date": "05/24/2021",
                                "destinationairport": "LAX",
                                "equipment": "738",
                                "flight": "AA655",
                                "flighttime": 5383,
                                "name": "American Airlines",
                                "price": 672.88,
                                "sourceairport": "SFO",
                                "utc": "11:42:00"
                              },
                              {
                                "date": "05/28/2021",
                                "destinationairport": "SFO",
                                "equipment": "738",
                                "flight": "AA344",
                                "flighttime": 6081,
                                "name": "American Airlines",
                                "price": 760.13,
                                "sourceairport": "LAX",
                                "utc": "20:47:00"
                              }
                            ]
            401:
              description: Returns an authentication error
              content:
                application/json:
                    schema: 
                      $ref: '#/components/schemas/Error'
        security:
            - bearer: []
        """
        agent = lowercase(tenant)

        scope = bucket.scope(agent)
        users = scope.collection('users')
        flights = scope.collection('bookings')

        # HTTP token authentication
        bearer = request.headers['Authorization']
        if not auth(bearer, username):
            return abortmsg(401, 'Username does not match token username: ' + username)
        
        try:
            userDocumentKey = lowercase(username)
            
            # The lookup does both a 'get' and an 'exists' in the same op. This
            # avoids having to handle a 'PathNotFoundException'.

            lookupResult = users.lookup_in(
              userDocumentKey,
              [
                SD.get('bookings'),
                SD.exists('bookings')
              ])
            
            bookedFlightKeys = []
            if lookupResult.exists(1):
                bookedFlightKeys = lookupResult.content_as[list](0)

            # GET requests are now performed to get the content of the bookings

            rows = []
            for key in bookedFlightKeys:
                rows.append(flights.get(key).content_as[dict])

            queryType = f"KV get - scoped to {scope.name}.users: for {len(bookedFlightKeys)} bookings in document "
            response = make_response(jsonify({"data": rows, "context": [queryType + userDocumentKey]}))
            return response
        
        except DocumentNotFoundException:
            return abortmsg(401, "User does not exist")

    @api.route('/tenants/<tenant>/user/<username>/flights', methods=['PUT', 'OPTIONS'])
    @cross_origin(supports_credentials=True)
    def updateflights(tenant, username):
        """Book a new flight for a user
        ---
        tags:
        - tenants
        parameters:
            - name: tenant
              in: path
              required: true
              schema:
                type: string
              example: tenant_agent_00
              description: Tenant agent name
            - name: username
              in: path
              required: true
              schema:
                type: string
              example: user1
              description: Username
        requestBody:
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    flights:
                      type: array
                      format: string
                      example: [{
                                  "name": "boeing",
                                  "flight": "12RF",
                                  "price": 50.0,
                                  "date": "12/12/2020",
                                  "sourceairport": "London (Gatwick)",
                                  "destinationairport": "Leonardo Da Vinci International Airport"
                               }]
        responses:
            200:
              description: Returns flight data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultSingleton'
                  example:
                    context: ["KV update - scoped to tenant_agent_00.users: for bookings field in document user1"]
                    data:
                      added: [{
                               "date": "12/12/2020",
                               "destinationairport": "Leonardo Da Vinci International Airport",
                               "flight": "12RF",
                               "name": "boeing",
                               "price": 50.0,
                               "sourceairport": "London (Gatwick)"
                             }]
            401:
              description: Returns an authentication error
              content:
                application/json:
                    schema: 
                      $ref: '#/components/schemas/Error'
        security:
            - bearer: []
        """
        agent = lowercase(tenant)
        user = lowercase(username)

        scope = bucket.scope(agent)
        users = scope.collection('users')
        bookings = scope.collection('bookings')

        queryType = f"KV update - scoped to {scope.name}.users: for bookings field in document "

        # HTTP token authentication
        bearer = request.headers['Authorization']
        if not auth(bearer, username):
            return abortmsg(401, 'Username does not match token username: ' + username)
        
        # Add the flight details to a new document in the bookings collection.

        try:
            flightData = request.get_json()['flights'][0]
            flightID = str(uuid.uuid4())
            bookings.upsert(flightID, flightData)

        except Exception as e:
            print(e, flush=True)
            return abortmsg(500, "Failed to add flight data")
        
        # The booking is document not associated with a user. A Sub-Document op
        # is performed to add the key of the booking document to the 'bookings'
        # field in the given user's document.
        
        try:
            users.mutate_in(user, (SD.array_append('bookings', flightID, create_parents=True),))
            resultJSON = {'data': {'added': [flightData]},
                          'context': [queryType + user]}
            return make_response(jsonify(resultJSON))
        
        except DocumentNotFoundException:
            return abortmsg(401, "User does not exist")
        except Exception:
            return abortmsg(500, "Couldn't update flights")


class HotelView(SwaggerView):
    """Class for storing Hotel search related information"""

    @api.route('/hotels/<description>/<location>/', methods=['GET'])
    @cross_origin(supports_credentials=True)
    def hotels(description, location):
        # Requires FTS index called 'hotels-index'
        # TODO auto create index if missing
        """Find hotels using full text search
        ---
        tags:
        - hotels
        parameters:
            - name: description 
              in: path
              required: false
              schema:
                type: string
              example: pool
              description: Hotel description keywords
            - name: location
              in: path
              required: false
              schema:
                type: string
              example: San Francisco
              description: Hotel location 
        responses:
            200:
              description: Returns hotel data and query context information
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/ResultList'
                  example:
                    context: ["FTS search - scoped to: inventory.hotel within fields address,city,state,country,name,description"]
                    data: [
                            {
                              "address": "250 Beach St, San Francisco, California, United States",
                              "description": "Nice hotel, centrally located (only two blocks from Pier 39). Heated outdoor swimming pool.",
                              "name": "Radisson Hotel Fisherman's Wharf"
                            },
                            {
                              "address": "121 7th St, San Francisco, California, United States",
                              "description": "Chain motel with a few more amenities than the typical Best Western; outdoor swimming pool,
                                  internet access, cafe on-site, pet friendly.",
                              "name": "Best Western Americania"
                            }
                         ]
        """ 
        queryPrep = FT.ConjunctionQuery()
        if location != '*' and location != "":
            queryPrep.conjuncts.append(
                FT.DisjunctionQuery(
                    FT.MatchPhraseQuery(location, field='country'),
                    FT.MatchPhraseQuery(location, field='city'),
                    FT.MatchPhraseQuery(location, field='state'),
                    FT.MatchPhraseQuery(location, field='address')
                ))

        if description != '*' and description != "":
            queryPrep.conjuncts.append(
                FT.DisjunctionQuery(
                    FT.MatchPhraseQuery(description, field='description'),
                    FT.MatchPhraseQuery(description, field='name')
                ))
        
        # Attempting to run a compound query with no sub-queries will result in
        # a 'NoChildrenException'.

        if len(queryPrep.conjuncts) == 0:
            queryType = "FTS search rejected - no search terms were provided"
            response = {'data': [], 'context': [queryType]}
            return jsonify(response)
            
        searchRows = cluster.search_query('hotels-index', 
                                          queryPrep, 
                                          SearchOptions(limit=100))

        # The 'SearchResult' object returned by the search does not contain the
        # full document, consisting of just matches and metadata. This metadata
        # includes the document key, so sub-document operations retrieve all of
        # the fields needed by the frontend.

        allResults = []
        addressFields = ['address', 'city', 'state', 'country']
        dataFields = ['name', 'description']

        scope = bucket.scope('inventory')
        hotel_collection = scope.collection('hotel')

        for hotel in searchRows:
            
            # The lookup will succeed even if the document does not contain all
            # fields. Attempting to read these none existent fields will result
            # in a 'DocumentNotFoundException'.

            hotelFields = hotel_collection.lookup_in(
                hotel.id, [SD.get(x) for x in [*addressFields, *dataFields]])

            # Concatenates the first 4 fields to form the address. 

            hotelAddress = []
            for x in range(len(addressFields)):
                try:
                    hotelAddress.append(hotelFields.content_as[str](x))
                except:
                    pass
            hotelAddress = ', '.join(hotelAddress)

            # Extracts the other fields.

            hotelData = {}
            for x, field in enumerate(dataFields):
                try:    
                    hotelData[field] = hotelFields.content_as[str](x+len(addressFields))
                except:
                    pass
                
            hotelData['address'] = hotelAddress
            allResults.append(hotelData)

        queryType = f"FTS search - scoped to: {scope.name}.hotel within fields {','.join([*addressFields, *dataFields])}"
        response = {'data': allResults, 'context': [queryType]}
        return jsonify(response)


def abortmsg(code, message):
    response = jsonify({'message': message})
    response.status_code = code
    return response


def convdate(rawdate):
    """Returns integer data from mm/dd/YYYY"""
    day = datetime.strptime(rawdate, '%m/%d/%Y')
    return day.weekday()


def genToken(username):
    return jwt.encode({'user': username}, JWT_SECRET, algorithm='HS256').decode("ascii")


def auth(bearerHeader, username):
    bearer = bearerHeader.split(" ")[1]
    return username == jwt.decode(bearer, JWT_SECRET)['user']


def connect_db():
    print(CONNSTR, authenticator)
    cluster = Cluster(CONNSTR, ClusterOptions(authenticator))
    bucket = cluster.bucket('travel-sample')
    return cluster, bucket


if __name__ == "__main__":
    cluster, bucket = connect_db()
    app.register_blueprint(api, url_prefix="/api")
    swagger = Swagger(app, template=swagger_template)
    app.run(debug=True, host='0.0.0.0', port=8080, threaded=False)