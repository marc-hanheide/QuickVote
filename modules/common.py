from pymongo import DESCENDING	# for indexing in decending order
from pymongo import ASCENDING
from json import dumps
from bson import json_util
import httpagentparser
from datetime import datetime	# for getting the current time
import web
renderer = web.template.render('templates', base="base", globals=globals())
# hashing
import hmac
import hashlib
import random
import string

# UUID4
from uuid import uuid4

# database globals
from threading import Condition
from pymongo import MongoClient

import modules.config as config
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
