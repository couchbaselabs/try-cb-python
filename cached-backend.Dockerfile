FROM python:3.9-slim-bullseye

LABEL maintainer="Couchbase"

WORKDIR /app
# Copies the code to the container (cached service in compose is not mounted)
COPY . /app/

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libssl-dev \
    jq curl

RUN pip install -r requirements.txt

# Expose ports
EXPOSE 8080

# Set the entrypoint 
ENTRYPOINT ["./wait-for-couchbase.sh", "python", "travel.py"]