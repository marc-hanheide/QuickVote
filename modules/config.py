import os

if 'DB_PORT_27017_TCP_ADDR' in os.environ:
    mongo_host = os.environ['DB_PORT_27017_TCP_ADDR']
else:
    mongo_host = 'localhost'

if 'DB_PORT_27017_TCP_PORT' in os.environ:
    mongo_port = int(os.environ['DB_PORT_27017_TCP_PORT'])
else:
    mongo_port = 27017

if 'QV_PORT' in os.environ:
    listen_port = int(os.environ['QV_PORT'])
else:
    listen_port = 5000

if 'QV_BASE_URL' in os.environ:
    base_url = os.environ['QV_BASE_URL']
else:
    base_url = "http://localhost:%d/" % listen_port

# dummy data to stop proxy buffering
dummy_data = range(0, 20480)
