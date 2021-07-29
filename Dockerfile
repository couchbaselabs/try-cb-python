FROM python:3.9-slim-buster

LABEL maintainer="Couchbase"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential cmake \
    git-all libssl-dev \
    jq curl

ADD . /app 

RUN pip install -r requirements.txt

# Expose ports
EXPOSE 8080

# Set the entrypoint 
ENTRYPOINT ["./wait-for-couchbase.sh", "python", "travel.py"]
