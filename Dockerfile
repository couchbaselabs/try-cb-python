# Set the base image to Ubuntu
FROM ubuntu:20.04

# File Author / Maintainer
LABEL org.opencontainers.image.authors="Couchbase"

# Update the sources list
RUN apt-get update

# Install basic applications
RUN apt-get install -y inetutils-ping git python3-pip

# Get application and run it
# RUN git clone -b mobile-travel-sample-m1  https://github.com/couchbaselabs/try-cb-python.git
COPY . ./try-cb-python
WORKDIR "/try-cb-python"
RUN pip3 install -r requirements.txt

# Expose ports
EXPOSE 80

# Set the default command to execute    
# when creating a new container
# i.e. using CherryPy to serve the application
CMD python3 travel.py -c cb-server -s sync-gateway
