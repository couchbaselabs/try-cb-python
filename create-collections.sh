
# create bucket
curl -X POST -u $1:$2 http://$3:8091/pools/default/buckets -d name=default -d ramQuotaMB=100

# create scope
curl -u $1:$2 -X POST http://$3:8091/pools/default/buckets/default/collections -d name=larson-travel

# create collections in each scope
curl -u $1:$2 -X POST http://$3:8091/pools/default/buckets/default/collections/larson-travel -d name=users
curl -u $1:$2 -X POST http://$3:8091/pools/default/buckets/default/collections/larson-travel -d name=flights

# show what we have made
echo '\n\n\n\nTHE FINAL RESULT'
curl -u $1:$2 -X GET http://$3:8091/pools/default/buckets/default/collections
echo '\n'