# Set the base image to Ubuntu
FROM ubuntu

# File Author / Maintainer
MAINTAINER Couchbase

# Update the sources list
RUN apt-get update

# Install basic applications
RUN apt-get install -y tar git curl nano wget dialog net-tools build-essential dpkg

RUN apt-get install apt-utils --assume-yes
RUN apt-get install lsb-release --assume-yes

# Install Python and Basic Python Tools
RUN apt-get update && apt-get install -y python python-dev python-distribute python-pip
RUN wget http://packages.couchbase.com/releases/couchbase-release/couchbase-release-1.0-2-amd64.deb && apt-get install ./couchbase-release-1.0-2-amd64.deb

RUN apt-get update && apt-get install libcouchbase-dev build-essential python-dev python-pip --assume-yes

ADD . .

# Get pip to download and install requirements:
RUN pip install -r requirements.txt

# Expose ports
EXPOSE 80

# Set the default command to execute    
# when creating a new container
# i.e. using CherryPy to serve the application
CMD python travel.py
