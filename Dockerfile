FROM python:3.9-slim-buster

LABEL maintainer="Couchbase"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential cmake \
    git-all libssl-dev \
    jq curl

ADD . /app 

# Due to some compatibility issues with Couchbase Server 7.0.0 beta and SDK 3.1.1, 
# we set the LCB_TAG (libcouchbase tag) to 3.1.0 to mitigate against `LCB_ERR_KVENGINE_INVALID_PACKET` error(PYCBC-1119).
# Get pip to download and install requirements:
RUN LCB_TAG=3.1.0 pip install -r requirements.txt

# Expose ports
EXPOSE 8080

# Set the entrypoint 
ENTRYPOINT ["./entrypoint.sh"]
