#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from pymongo import MongoClient
from uuid import uuid4

urls = (
    '/', 'index',
    '/submit', 'submit'

)

question_global = {
    'uuid': uuid4(),
    'question': "What is the meaning of live?",
    'answers': ['A', 'B', 'C', 'D'],
    'correct': ['A, B']
}


client = MongoClient('10.210.9.130', 27017)

qv_db = client['QuickVote']

qv_collection = qv_db['answers']


renderer = web.template.render('templates', base="base", globals=globals())
app = web.application(urls, globals())


class index:
    def GET(self):
        return renderer.index()


class submit:
    def POST(self):
        print web.input()
        qv_collection.insert_one(web.input())
        return renderer.submit()
        #return web.seeother('/')


def signal_handler(signum, frame):
    app.stop()
    print "stopped."


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
