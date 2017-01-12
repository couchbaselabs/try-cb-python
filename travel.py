from datetime import datetime
import math
from random import random
import jwt  # from PyJWT

from flask import Flask, request, jsonify, abort
from flask import make_response, redirect
from flask.views import View
from flask_classy import FlaskView, route

from couchbase.bucket import Bucket
from couchbase.n1ql import N1QLQuery
from couchbase.exceptions import NotFoundError, CouchbaseNetworkError, \
    CouchbaseTransientError, CouchbaseDataError, SubdocPathNotFoundError
import couchbase.fulltext as FT
import couchbase.subdocument as SD

CONNSTR = 'couchbase://localhost/travel-sample'
PASSWORD = ''

app = Flask(__name__, static_url_path='/static')

@app.route('/')
@app.route('/static/')
def index():
    return redirect("/static/index.html", code=302)

app.config.from_object(__name__)

def make_user_key(username):
    return 'user::' + username


class Airport(View):
    """Airport class for airport objects in the database"""

    def findall(self):
        """Returns list of matching airports and the source query"""
        querystr = request.args['search'].lower()
        queryprep = "SELECT airportname FROM `travel-sample` WHERE "
        if len(querystr) == 3:
            queryprep += "LOWER(faa) = $1"
            queryargs = [querystr]
        elif len(querystr) == 4:
            queryprep += "LOWER(icao) = $1"
            queryargs = [querystr]
        else:
            queryprep += "LOWER(airportname) LIKE $1"
            queryargs = ['%' + querystr + '%']

        res = db.n1ql_query(N1QLQuery(queryprep, *queryargs))
        airportslist = [x for x in res]
        context = [queryprep]

        response = make_response(
            jsonify({"data": airportslist, "context": context}))
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

        res = db.n1ql_query(N1QLQuery(queryprep, fromloc, toloc))
        flightpathlist = [x for x in res]

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
        resroutes = db.n1ql_query(
            N1QLQuery(queryroutes, queryto, queryfrom, queryleave))
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
            doc_pass = db.retrieve_in(userdockey, 'password')[0]
            if doc_pass != password:
                return abortmsg(401, "Password does not match")
            else:
                token = jwt.encode({'user': user}, 'cbtravelsample')
                return jsonify({'data': {'token': token}})

        except SubdocPathNotFoundError:
            print("Password for user {} item does not exist".format(
                userdockey))
        except NotFoundError:
            print("User {} item does not exist".format(userdockey))
        except CouchbaseTransientError:
            print("Transient error received - has Couchbase stopped running?")
        except CouchbaseNetworkError:
            print("Network error received - is Couchbase Server running on this host?")

        token = jwt.encode({'user': user}, 'cbtravelsample')
        return jsonify({'data': {'token': token}})

    @route('/signup', methods=['POST', 'OPTIONS'])
    def signup(self):
        """Signup a new user"""
        req = request.get_json()
        user = req['user'].lower()
        password = req['password']
        userrec = {'username': user, 'password': password}

        try:
            db.upsert(make_user_key(user), userrec)
            token = jwt.encode({'user': user}, 'cbtravelsample')
            respjson = jsonify({'data': {'token': token}})
        except CouchbaseDataError as e:
            abort(409)
        response = make_response(respjson)
        return response

    @route('/<username>/flights', methods=['GET', 'POST', 'OPTIONS'])
    def userflights(self, username):
        """List the flights that have been reserved by a user"""
        if request.method == 'GET':
            token = jwt.encode({'user': username}, 'cbtravelsample')
            bearer = request.headers['Authentication'].split(" ")[1]
            if token != bearer:
                return abortmsg(401, 'Username does not match token username')

            try:
                userdockey = make_user_key(username)
                subdoc = db.retrieve_in(userdockey, 'flights')
                flights = subdoc.get('flights', [])
                respjson = jsonify({'data': flights[1]})
                response = make_response(respjson)
                return response
            except NotFoundError:
                return abortmsg(500, "User does not exist")

        elif request.method == 'POST':
            userdockey = make_user_key(username)

            token = jwt.encode({'user': username}, 'cbtravelsample')
            bearer = request.headers['Authentication'].split(" ")[1]

            if token != bearer:
                return abortmsg(401, 'Username does not match token username')

            newflights = request.get_json()['flights'][0]

            try:
                db.mutate_in(userdockey,
                             SD.array_append('flights',
                                             newflights, create_parents=True))
                resjson = {'data': {'added': newflights},
                           'context': 'Update document ' + userdockey}
                return make_response(jsonify(resjson))
            except NotFoundError:
                return abortmsg(500, "User does not exist")
            except CouchbaseDataError:
                abortmsg(409, "Couldn't update flights")


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

        q = db.search('hotels', qp, limit=100)
        results = []
        for row in q:
            subdoc = db.retrieve_in(row['id'], 'country', 'city', 'state',
                                    'address', 'name', 'description')

        # Get the fields from the document, if they exist
        addr = ', '.join(x for x in (
            subdoc.get(y)[1] for y in ('address', 'city', 'state', 'country')) if x)
        subresults = {'name': subdoc['name'], 'description': subdoc['description'], 'address': addr}
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


# Setup pluggable Flask views routing system
HotelView.register(app, route_prefix='/api/')
# Added route_base below to allow camelCase view name
FlightPathsView.register(app, route_prefix='/api/', route_base='flightPaths')
UserView.register(app, route_prefix='/api/')

app.add_url_rule('/api/airports', view_func=Airport.as_view('airports'),
                 methods=['GET', 'OPTIONS'])


def connect_db():
    return Bucket(CONNSTR, password=PASSWORD)


db = connect_db()

if __name__ == "__main__":
    app.run(debug=False, host='localhost', port=8080)
