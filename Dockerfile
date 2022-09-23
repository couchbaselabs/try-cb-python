# Set the base image to Ubuntu
FROM ubuntu:18.04

# File Author / Maintainer
LABEL org.opencontainers.image.authors="Couchbase"

# Update the sources list
RUN apt-get update

# Install basic applications
RUN apt-get install -y tar git curl nano wget dialog net-tools build-essential dpkg

RUN apt-get install apt-utils --assume-yes
RUN apt-get install lsb-release --assume-yes

# Install Python and Basic Python Tools
RUN apt-get update && apt-get install -y python3 python3-dev python-distribute python3-pip python3-setuptools cmake
RUN wget http://packages.couchbase.com/releases/couchbase-release/couchbase-release-1.0-6-amd64.deb && apt-get install ./couchbase-release-1.0-6-amd64.deb

RUN wget https://packages.couchbase.com/clients/c/libcouchbase-3.0.1_ubuntu1604_xenial_amd64.tar
RUN tar -xf libcouchbase-3.0.1_ubuntu1604_xenial_amd64.tar

RUN cd libcouchbase-3.0.1_ubuntu1604_xenial_amd64 && apt-get update && apt-get install -y  libevent-core-2.1 ./libcouchbase3_3.0.1*.deb  ./libcouchbase-dev*.deb 

ADD . .

# Get pip to download and install requirements:
RUN pip3 install -r requirements.txt

# Expose ports
EXPOSE 80

# Set the default command to execute    
# when creating a new container
# i.e. using CherryPy to serve the application
CMD python3 travel.py
