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
RUN apt-get update && apt-get install -y python3 python3-dev python-distribute python3-pip python3-setuptools cmake
RUN wget http://packages.couchbase.com/releases/couchbase-release/couchbase-release-1.0-6-amd64.deb && apt-get install ./couchbase-release-1.0-6-amd64.deb

RUN wget https://packages.couchbase.com/clients/c/libcouchbase-3.0.0_ubuntu1604_xenial_amd64.tar
RUN tar -xf libcouchbase-3.0.0_ubuntu1604_xenial_amd64.tar

RUN cd libcouchbase-3.0.0_ubuntu1604_xenial_amd64 && apt install libevent-core-2.1 ./libcouchbase3_3.0.0*.deb  ./libcouchbase-dev*.deb 

#RUN apt-get install libevent-core-2.1 && cd libcouchbase-3.0.0_ubuntu1604_xenial_amd64 && apt install ./libcouchbase3_3.0.0*.deb || true && dpkg -i libcouchbase3-libevent*_3.0.0*.deb || true && dpkg -i libcouchbase3-tools*_3.0.0*.deb || true && dpkg -i libcouchbase-dev*.deb || true

#RUN apt-get update && apt-get install  libcouchbase-dev libcouchbase3 --assume-yes

#RUN apt-get update && apt-get install libevent-core-2.1 --assume-yes



#RUN cd libcouchbase-3.0.0_ubuntu1604_xenial_amd64 && pwd && ls && dpkg  -i libcouchbase3*_*.deb libcouchbase3-tools_3.0.0*.deb libcouchbase3-libevent_3.0.0*.deb libcouchbase-dev_*.deb

#RUN 'dpkg -i libcouchbase-dev_3.0.0-1_amd64.deb && dpkg -i libcouchbase3{-tools,-libevent,}_3.0.0*.deb'

#RUN dpkg -i libcouchbase-3.0.0_ubuntu1604_xenial_amd64/libcouchbase-dev_3.0.0-1_amd64.deb && dpkg -i libcouchbase3{-tools,-libevent,}_3.0.0*.deb
#RUN dpkg -i libcouchbase3{-tools,-libevent,}_3.0.0*.deb libcouchbase-dev_3.0.0-1_amd64.deb

#RUN apt-get update && apt-get install libcouchbase-dev build-essential python-dev python-pip --assume-yes

ADD . .

# Get pip to download and install requirements:
RUN pip3 install -r requirements.txt

# Expose ports
EXPOSE 80

# Set the default command to execute    
# when creating a new container
# i.e. using CherryPy to serve the application
CMD python3 travel.py
