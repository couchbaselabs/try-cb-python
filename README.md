# Couchbase Python travel-sample Application REST Backend
This is a sample application for getting started with Couchbase Server and the Python SDK. 
The application runs a single page web UI for demonstrating SQL for Documents (N1QL), Sub-document requests and Full Text Search (FTS) querying capabilities. 
It uses Couchbase Server together with the Python Flask web platform, Vue and Bootstrap.

The application is a flight planner that allows the user to search for and select a flight route (including the return flight) based on airports and dates. 
Airport selection is done dynamically using an autocomplete box bound to N1QL queries on the server side. After selecting a date, it then searches 
for applicable air flight routes from a previously populated database. An additional page allows users to search for Hotels using less structured keywords.

![Application](app.png)

## Prerequisites
You will need [Docker](https://docs.docker.com/get-docker/) installed on your machine in order to run this application as we have defined a [_Dockerfile_](Dockerfile) and a [_docker-compose.yml_](docker-compose.yml) to run Couchbase Server 7.0.0-beta, the front-end [Vue app](https://github.com/couchbaselabs/try-cb-frontend-v2.git) and the Python REST API.

If you wish to run this application against your own configuration of Couchbase Server, you will need version 7.0.0-beta or later with the `travel-sample` bucket setup.

## Running the application
To download the application you can either download [the archive](https://github.com/couchbaselabs/try-cb-python/archive/master.zip) or clone the repository:

```
$ git clone https://github.com/couchbaselabs/try-cb-python.git
```

The backend application uses several Python libraries that need to be installed, luckily this is all taken care of by the Dockerfile provided.

To launch the full application you can simply run this command from a terminal:

```
$ docker-compose up
```

> **_NOTE:_** When you run the application for the first time, it will pull/build the relevant docker images, so it might take a bit of time.

This will start the Python backend, Couchbase Server 7.0.0-beta and the Vue app.
You can access the backend API on `http://localhost:8080/`, the UI on `http://localhost:8081/` and Couchbase Server at `http://localhost:8091/`.

You should then be able to browse the UI, search for US airports and get flight route information. If you are unsure for what to search for, try from SFO to LAX.

Alternatively, you can choose to only run the backend API and Couchbase Server if that is your preference:
```
docker-compose up backend
```

If you wish to run the application against a different setup of Couchbase Server
you can simply run `docker-compose up` with commandline arguments.

```
$ CB_HOST=10.144.211.101 CB_USER=Administrator CB_PSWD=password docker-compose up 
```

To end the application press CONTROL+C in the terminal and wait for docker-compose to gracefully stop your containers.

## Configuration Options

By default the application will use the `travel-sample.inventory` scope to query/search flight and hotel data.

It will also separate user account data such as flight bookings and credentials in the `tenant_agent_XX scopes`.  

These options can be modified in `travel.py`.
