from pymongo import DESCENDING	# for indexing in decending order
from datetime import datetime	# for getting the current time

# UUID4
from uuid import uuid4

# database globals
from threading import Condition
from pymongo import MongoClient

import config
client = MongoClient(config.mongo_host, config.mongo_port)

new_input = Condition()

qv_db = client['QuickVote']

qv_collection = qv_db['answers']
qv_collection.create_index('uuid')
qv_collection.create_index('session')
qv_collection.create_index('domain')
qv_collection.create_index('inserted_at')

qv_questions = qv_db['questions']
qv_questions.create_index('uuid', unique=True)
qv_questions.create_index('domain')
