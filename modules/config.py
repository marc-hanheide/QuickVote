import os

listen_port = 5000

if 'DB_PORT_27017_TCP_ADDR' in os.environ:
    mongo_host = os.environ['DB_PORT_27017_TCP_ADDR']
    mongo_port = 27017
else:
    mongo_host = 'localhost'
    mongo_port = 27017

if 'QV_BASE_URL' in os.environ:
    base_url = os.environ['QV_BASE_URL']
else:
    base_url = "http://localhost"
    if listen_port != 80 or listen_port != 443: # if the port is required in the URL, add it
        base_url = base_url + ":" + str(listen_port)  # e.g. http://localhost:5000
    base_url = base_url + "/" # Needs a trailing slash at the end...

 # dummy data to stop proxy buffering
dummy_data = range(0, 20480)
