from datetime import datetime
import math
from random import random
import jwt  # from PyJWT

from flask import Flask, request, jsonify, abort
from flask import make_response
from flask.views import View
from flask_classy import FlaskView, route

from couchbase.bucket import Bucket
from couchbase.n1ql import N1QLQuery
from couchbase.exceptions import NotFoundError, CouchbaseNetworkError, \
    CouchbaseTransientError, CouchbaseDataError
import couchbase.fulltext as FT
import couchbase.subdocument as SD

from crossdomain_helper import crossdomain

CONNSTR = 'couchbase://localhost/travel-sample'
PASSWORD = ''

app = Flask(__name__, static_url_path='/static')

app.config.from_object(__name__)


def make_user_key(username):
    return 'user::' + username


class Airport(View):
    """Airport class for airport objects in the database"""

    # @app.route('/api/airports?search=<search>')
    # @route('/airports?search=<search>', methods=['GET','OPTIONS'])
    # @route is defined explicitly as a add_route way below...
    @crossdomain(origin='*', headers='content-type')
    def findall(self):
        """Returns list of matching airports and the source query"""
        print("Airport findall")
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

    # GET /api/flightPaths/{from}/{to}?leave=mm/dd/YYYY
    # http://localhost:5000/api/flightpaths/Nome/City?leave=01/01/2016
    @route('/<fromloc>/<toloc>', methods=['GET', 'OPTIONS'])
    @crossdomain(origin='*', headers='content-type')
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
    @crossdomain(origin='*', headers='content-type')
    def login(self):
        req = request.get_json()
        user = req['user'].lower()
        password = req['password']
        userdockey = make_user_key(user)

        try:
            doc = db.get(userdockey)
            if 'password' in doc.value:
                print("doc pass: {}, supplied: {}".format(
                    doc.value['password'], password))
                if doc.value['password'] != password:
                    return abortmsg(401, "Password does not match")
                else:
                    token = jwt.encode({'user': user}, 'cbtravelsample')
                    return jsonify({'data': {'token': token}})
            else:
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
    @crossdomain(origin='*', headers='content-type')
    def signup(self):
        req = request.get_json()
        user = req['user'].lower()
        password = req['password']
        # user = request.args['user'].lower()
        # password = hashlib.md5(request.args['password']).hexdigest()
        userrec = {'username': user, 'password': password}

        try:
            db.upsert(make_user_key(user), userrec)
            token = jwt.encode({'user': user}, 'cbtravelsample')
            respjson = jsonify({'data': {'token': token}})
        except CouchbaseDataError as e:
            for result in e.all_results.items():
                if not result.success:
                    abort(409)
        response = make_response(respjson)
        return response

    @route('/<username>/flights', methods=['GET', 'POST', 'OPTIONS'])
    @crossdomain(origin='*', headers='content-type')
    def userflights(self, username):
        print("request: " + request.method)
        if request.method == 'GET':
            print('userflights: get')
            # TODO implement JWT check?
            req = request.get_json()
            user = req['user'].lower()
            password = req['password']
            userdockey = make_user_key(user)

            if username != user:
                return abortmsg(401, 'Username does not match token username')

            try:
                doc = db.get(userdockey)
                if 'password' in doc.value:
                    if doc.value['password'] != password:
                        return abortmsg(401, "Password does not match")
                    else:
                        # Password match..
                        userrec = doc.value
                        if 'flights' not in userrec:
                            userrec["flights"] = []
                        flights = userrec["flights"]
                        respjson = jsonify({'data': flights})
                        response = make_response(respjson)
                        return response
                else:
                    return abortmsg(500, "Password for user does not exist")
            except NotFoundError:
                return abortmsg(500, "User does not exist")

        elif request.method == 'POST':
            print('userflights: post')

            req = request.get_json()
            for r in req['flights']:
                print(r)
            userdockey = make_user_key(username)

            token = jwt.encode({'user': username}, 'cbtravelsample')
            bearer = request.headers['Authentication'].split(" ")[1]

            if token != bearer:
                return abortmsg(401, 'Username does not match token username')

            newflights = request.get_json()['flights'][0]

            try:
                doc = db.get(userdockey)
                userrec = doc.value
                if 'flights' not in userrec:
                    userrec["flights"] = []

                userrec["flights"].append(newflights)
                try:
                    db.upsert(userdockey, userrec)
                    print("Upsert: " + str(userrec))
                    resjson = {'data': {'added': newflights},
                               'context': 'Update document ' + userdockey}

                except CouchbaseDataError as e:
                    for key, result in e.all_results.items():
                        if not result.success:
                            abortmsg(409, "User flights upsert failed")

                response = make_response(jsonify(resjson))
                return response

            except NotFoundError:
                return abortmsg(500, "User does not exist")


class HotelView(FlaskView):
    """Class for storing Hotel search related information"""

    # @route('/api/hotel/<description>/<location>',  methods=['GET'])

    @route('/<description>/<location>', methods=['GET'])
    def findall(self, description, location):
        # Requires FTS index called 'hotels', but there is already travel-search index?
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
        # {u'sort': [u'_score'], u'index': u'hotels_42f1b46e30915726_b7ff6b68', u'score': 2.1213794760780034, u'id': u'hotel_25167', u'locations': {
        # u'city': {u'san': [{u'start': 0, u'end': 3, u'pos': 1, u'array_positions': None}]}, u'type': {u'hotel': [{u'start': 0, u'end': 5, u'pos':
        # 1, u'array_positions': None}]}, u'name': {u'hyatt': [{u'start': 17, u'end': 22, u'pos': 3, u'array_positions': None}]}}}

        results = []
        for row in q:
            subdoc = db.lookup_in(row['id'], SD.get('country'), SD.get('city'),
                                  SD.get('state'), SD.get('address'),
                                  SD.get('name'), SD.get('description'))
            # SubdocResult<rc=0x0, key=u'hotel_25167', cas=0xb0c156f90001, specs=(Spec<GET, 'country'>, Spec<GET, 'city'>, Spec<GET, 'state'>, Spec<GET,
            # 'address'>, Spec<GET, 'name'>, Spec<GET, 'description'>), results=[(0, u'United States'), (0, u'San Diego'), (0, u'California'), (0, u'1
            # Market Place'), (0, u'Manchester Grand Hyatt'), (0, u'This hotel has over 1600 rooms, making it the largest hotel in San Diego. Located ne
            # xt to the Convention Center, consisting of two towers that are connected on the bottom four floors.')]>

            subresults = {'name': subdoc['name'],
                          'address': subdoc['address'] + ', ' + subdoc[
                              'city'] + ', ' + subdoc['country'],
                          'description': subdoc['description']}
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
    app.run(debug=False, host='0.0.0.0', port=8080)