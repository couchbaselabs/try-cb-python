FROM python:3.9-slim-buster

LABEL maintainer="Couchbase"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential cmake \
    git-all python3-dev python3-pip \
    python3-setuptools \
    jq curl

ADD . /app 

# Get pip to download and install requirements:
RUN pip install -r requirements.txt

# Expose ports
EXPOSE 8080

# Set the entrypoint 
ENTRYPOINT ["./entrypoint.sh"]
