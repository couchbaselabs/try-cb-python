FROM sample-app-python

# Expose ports
EXPOSE 8080

# Set the entrypoint 
ENTRYPOINT ["./wait-for-couchbase.sh", "python", "travel.py"]