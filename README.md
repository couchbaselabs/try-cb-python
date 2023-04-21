# Couchbase Python travel-sample Application REST Backend

This is a sample application for getting started with [Couchbase Server] and the [Python SDK].
The application runs a single page web UI for demonstrating SQL++ (N1QL), Sub-document requests and Full Text Search (FTS) querying capabilities.
It uses Couchbase Server together with the [Flask] web framework for [Python], [Swagger] for API documentation, [Vue] and [Bootstrap].

The application is a flight planner that allows the user to search for and select a flight route (including the return flight) based on airports and dates.
Airport selection is done dynamically using an autocomplete box bound to N1QL queries on the server side. After selecting a date, it then searches
for applicable air flight routes from a previously populated database. An additional page allows users to search for Hotels using less structured keywords.

![Application](app.png)

## Prerequisites

To download the application you can either download [the archive](https://github.com/couchbaselabs/try-cb-python/archive/master.zip) or clone the repository:

```
git clone https://github.com/couchbaselabs/try-cb-python.git
```

We recommend running the application with Docker, which starts up all components for you, but you can also run it in a Mix-and-Match style, which we'll describe below.

## Running the application with Docker

You will need [Docker](https://docs.docker.com/get-docker/) installed on your machine in order to run this application as we have defined a [_Dockerfile_](Dockerfile) and a [_docker-compose.yml_](docker-compose.yml) to run the three components required:

* `db`: the Couchbase Server 7.x
* `backend`: the Python REST API from this repository
* `frontend`: [Vue app](https://github.com/couchbaselabs/try-cb-frontend-v2.git) 

To launch all three components locally, you can simply run this command from a terminal:

```
docker-compose --profile local up
```
> **_NOTE:_** You may need more than the default RAM to run the images.
We have tested the travel-sample apps with 4.5 GB RAM configured in Docker's Preferences... -> Resources -> Memory.
When you run the application for the first time, it will pull/build the relevant docker images, so it might take a bit of time.

This will start the Python backend, Couchbase Server 7.0.0 and the Vue frontend app.

You can access the backend API on `http://localhost:8080/`, the UI on `http://localhost:8081/` and Couchbase Server at `http://localhost:8091/`.

```
❯ docker-compose --profile local up
...
Creating couchbase-sandbox-7.0.0      ... done
Creating try-cb-api                   ... done
Creating try-cb-fe                    ... done
Attaching to couchbase-sandbox-7.0.0, try-cb-api, try-cb-fe
couchbase-sandbox-7.0.0 | Starting Couchbase Server -- Web UI available at http://<ip>:8091
couchbase-sandbox-7.0.0 | and logs available in /opt/couchbase/var/lib/couchbase/logs
couchbase-sandbox-7.0.0 | Configuring Couchbase Server.  Please wait (~60 sec)...
try-cb-api  | wait-for-couchbase: checking http://db:8091/pools/default/buckets/travel-sample/
try-cb-api  | wait-for-couchbase: polling for '.scopes | map(.name) | contains(["inventory", "
try-cb-fe   | wait-for-it: waiting for backend:8080 without a timeout
try-cb-api  | wait-for-couchbase: ...
couchbase-sandbox-7.0.0 | Configuration completed!
couchbase-sandbox-7.0.0 | Couchbase Admin UI: http://localhost:8091 
couchbase-sandbox-7.0.0 | Login credentials: Administrator / password
try-cb-api  | wait-for-couchbase: checking http://db:8094/api/cfg
try-cb-api  | wait-for-couchbase: polling for '.status == "ok"'
try-cb-api  | wait-for-couchbase: checking http://db:8094/api/index/hotels-index
try-cb-api  | wait-for-couchbase: polling for '.status == "ok"'
try-cb-api  | wait-for-couchbase: Failure
try-cb-api  | wait-for-couchbase: Creating hotels-index...
try-cb-api  | wait-for-couchbase: checking http://db:8094/api/index/hotels-index/count
try-cb-api  | wait-for-couchbase: polling for '.count >= 917'
try-cb-api  | wait-for-couchbase: ...
try-cb-api  | wait-for-couchbase: ...
try-cb-api  | wait-for-couchbase: checking http://db:9102/api/v1/stats
try-cb-api  | wait-for-couchbase: polling for '.indexer.indexer_state == "Active"'
try-cb-api  | wait-for-couchbase: polling for '. | keys | contains(["travel-sample:def_airport
try-cb-api  | wait-for-couchbase: polling for '. | del(.indexer) | del(.["travel-sample:def_na
try-cb-api  | wait-for-couchbase: value is currently:
try-cb-api  | false
try-cb-api  | wait-for-couchbase: ...
try-cb-api  | wait-for-couchbase: polling for '. | del(.indexer) | map(.num_pending_requests =
try-cb-api  | Connecting to: couchbase://db
try-cb-api  | couchbase://db <couchbase.auth.PasswordAuthenticator object at 0x7f7a54d37580>
try-cb-api  |  * Serving Flask app "travel" (lazy loading)
try-cb-api  |  * Environment: production
try-cb-api  |    WARNING: This is a development server. Do not use it in a production deployment.
try-cb-api  |    Use a production WSGI server instead.
try-cb-api  |  * Debug mode: on
try-cb-api  |  * Running on http://0.0.0.0:8080/ (Press CTRL+C to quit)
try-cb-api  |  * Restarting with stat
try-cb-fe   | wait-for-it: backend:8080 is available after 73 seconds
try-cb-api  |  * Debugger is active!
try-cb-api  |  * Debugger PIN: 166-477-650
try-cb-fe   | 
try-cb-fe   | > try-cb-frontend-v2@0.1.0 serve
try-cb-fe   | > vue-cli-service serve --port 8081
try-cb-fe   | 
try-cb-fe   |  INFO  Starting development server...
try-cb-fe   |  DONE  Compiled successfully in 5623ms11:07:22 AM
try-cb-fe   | 
try-cb-fe   | 
try-cb-fe   |   App running at:
try-cb-fe   |   - Local:   http://localhost:8081/ 
try-cb-fe   | 
try-cb-fe   |   It seems you are running Vue CLI inside a container.
try-cb-fe   |   Access the dev server via http://localhost:<your container's external mapped port>/
try-cb-fe   | 
try-cb-fe   |   Note that the development build is not optimized.
try-cb-fe   |   To create a production build, run npm run build.
try-cb-fe   | 
```

You should then be able to browse the UI, search for US airports and get flight route information.

In order to make changes in the Python API and familiarize yourself with the SDK, you can update the `travel.py` file and save it. This will reload the backend server almost instantly.

To end the application press <kbd>Control</kbd>+<kbd>C</kbd> in the terminal and wait for docker-compose to gracefully stop your containers.

## Run the Database in Capella

To run the database in Couchbase Capella, the invocation is as straight-forward, but there are currently a few more setup steps:

```
CB_HOST={your-host-url} docker-compose --profile capella up
```

### Create the Capella Cluster

First, [sign up for a Capella account](https://docs.couchbase.com/cloud/get-started/get-started.html) and deploy a cluster.

The travel app uses the `travel-sample` data bucket, which is imported in the cluster by default. To check this, go to **Data Tools > Buckets**. You should see the `travel-sample` bucket with around 63k items.

If the bucket isn't present, you can import it manually. See [Import](https://docs.couchbase.com/cloud/clusters/data-service/import-data-documents.html) for information about how to import the `travel-sample` bucket.

### Create the Search index

1. Go to **Data Tools > Search > Create Search Index**
2. Click **Import from File**
3. Navigate to the try-cb-python directory, and select `fts-hotels-index.json`
4. Click **Create Index**

If you don't have access to the filesystem with the sample application backend, you can copy and paste the index defintion from [this repository](https://raw.githubusercontent.com/couchbaselabs/try-cb-python/HEAD/fts-hotels-index.json) into the **Index Definition** field.

### Create the Database Access

Create the credentials to log in **Settings > Database Access > Create Database Access**

* Access Name: cbdemo
* Secret: Password123!
* Bucket: travel-sample
* Scopes: All Scopes
* Access: read/write

Click **Create Database Access** to save your access credentials.

### Whitelist your IP

Go to **Settings > Allowed IP Ranges > Add Allowed IP**.

Enter the IP of the system you will be running the application on in the *Allowed IP* field. If this system is the same one you are accessing the Couchbase Capella Web Console on, you can click **Add Current IP Address**.

Click **Add Allowed IP** to add the IP address.

### Copy the Connection String

From the **Connect** tab, copy your cluster's connection string, which looks something like:

```
couchbases://cb.dmt-i0huhchusg9g.cloud.couchbase.com
```

### Start the backend and frontend

Run the following command to start the application.

```
CB_HOST={your-connection-string} docker-compose --profile capella up
```

You will only need to set the `CB_HOST` variable to point the backend to your database.
If you chose a different username and password than the demo ones, then you will also need to set these.

```
CB_HOST={your-connection-string}
# CB_USER=... 
# CB_PSWD=...

docker-compose --profile capella up
```

## Mix-and-Match services

In the provided `docker-compose.yml`, we've looked at the two profiles `local` and `capella` above.
As we saw, these set up dependencies between the services, to  sets up dependencies between the services to make startup as smooth and automatic as possible.
This means that by the time you log into the Frontend UI, the backend is ready to serve API calls, and the Couchbase database has all the data, indexes, and connections to serve the DB requests.

You have the flexibility to start any combination of `backend`,`frontend`, `db` via Docker, and take responsibility for starting the other services yourself. 
We'll look at a few useful scenarios here.

### Bring your own database

> **_NOTE:_** See above for specific details on running your database in Couchbase Capella.

If you wish to run this application against your own configuration of Couchbase Server, you will need version 7.0.0 or later with the `travel-sample` bucket setup.

First configure your database details:

```
CB_HOST=...
CB_USER=...
CB_PSWD=...
```

Then simply start the backend and frontend services only:

```
docker-compose up backend frontend
```

The `backend` docker service uses a wrapper we have provided called `wait-for-couchbase.sh` which checks the database state, and creates the Full Text Search index.

> **_NOTE_**: If you are choosing to run the backend without this wrapper, see below for how to create the index manually.

### Running the backend manually

If you want to run the Python API yourself without using Docker, you will need to ensure that you have `Python 3.7` or higher installed on your machine.
You may still use Docker to run the Database and Frontend components if desired.

Install the dependencies:

```
python3 -m pip install -r requirements.txt
```

If you already have an existing Couchbase server running and correctly configured, you might run:

```
python3 travel.py -c $CB_HOST -u $CB_USER -p $CB_PSWD
```

Note that the first time you run against a new database image, you may want to use the provided
`wait-for-couchbase.sh` wrapper to ensure that all indexes are created.

For example, using the Docker image provided:

```
docker-compose up db
export CB_HOST=localhost
export CB_USER=Administrator
export CB_PSWD=password
./wait-for-couchbase.sh echo Couchbase is ready!
python3 travel.py -c $CB_HOST -u $CB_USER -p $CB_PSWD
```

If you prefer, you may create the index manually, using Couchbase's REST API.

```
curl --fail -s -u $CB_USER:$CB_PSWD -X PUT \
        http://$CB_HOST:8094/api/index/hotels-index \
        -H 'cache-control: no-cache' \
        -H 'content-type: application/json' \
        -d @fts-hotels-index.json
```

Finally, if you want to see how the sample frontend Vue application works with your changes,
run it with:

```
docker-compose up frontend
```

### Running the frontend manually

To run the frontend components manually without Docker, follow the guide
[here](https://github.com/couchbaselabs/try-cb-frontend-v2)


## REST API reference, and tests.

All the travel-sample apps conform to the same interface, which means that they can all be used with the same database configuration and Vue.js frontend.

We've integrated Swagger/OpenApi version 3 documentation which can be accessed on the backend at `http://localhost:8080/apidocs` once you have started the app.

(You can also view a read-only version at https://docs.couchbase.com/python-sdk/current/hello-world/sample-application.html#)

To further ensure that every app conforms to the API, we have a [test suite][try-cb-test], which you can simply run with the command:

```
docker-compose --profile test up test
```

Best practice for running tests Mix-and-Match style are WIP. Something like the following might work on Mac:

```
BACKEND_BASE_URL=http://host.docker.internal:8080 docker-compose up test
```

Check the test repo for details on how to run locally.


[Couchbase Server]: https://www.couchbase.com/
[Python SDK]: https://docs.couchbase.com/python-sdk/current/hello-world/overview.html
[Flask]: https://flask.palletsprojects.com/en/2.0.x/
[Python]: https://www.python.org/
[Swagger]: https://swagger.io/resources/open-api/
[Vue]: https://vuejs.org/
[Bootstrap]: https://getbootstrap.com/
[try-cb-test]: https://github.com/couchbaselabs/try-cb-test/
