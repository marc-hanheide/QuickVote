#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps
from pymongo import MongoClient
from uuid import uuid4
from datetime import datetime
from bson import json_util

urls = (
    '/', 'index',
    '/submit', 'submit',
    '/admin', 'admin',
    '/results/(.*)', 'results',
    '/view/(.*)', 'view',
    '/editor', 'editor',
    '/questions/?(.*)', 'questions'
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
qv_questions = qv_db['questions']


renderer = web.template.render('templates', base="base", globals=globals())
app = web.application(urls, globals())


class index:
    def GET(self):
        uuid = question_global['uuid']
        try:
            qs = qv_questions.find_one({'uuid': uuid})
            return renderer.index(qs)
        except Exception as e:
            raise web.NotFound('error getting questionnaire: ' + e.message)


class submit:
    def POST(self):
        print web.input()
        qv_collection.insert_one(web.input())
        return renderer.submit()


class editor:

    def GET(self):
        qs = qv_questions.find({}).sort([('inserted_at', -1)])

        data = {
            'existing_questions': [],
            'new_uuid': uuid4()
        }

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.editor(data)


class questions:

    def POST(self, uuid=None):
        user_data = web.input()
        if hasattr(user_data, 'options') and \
           hasattr(user_data, 'correct') and \
           hasattr(user_data, 'question') and \
           hasattr(user_data, 'uuid'):
            options_str = user_data.options.split(',')
            correct_str = user_data.correct.split(',')
            doc = {
                'options': [o.strip() for o in options_str],
                'correct': [o.strip() for o in correct_str],
                'question': user_data.question,
                'uuid': user_data.uuid,
                'inserted_at': datetime.now()
            }
            if len(user_data.question) > 0:
                qv_questions.replace_one({'uuid': user_data.uuid},
                                         doc, upsert=True)
            else:
                qv_questions.remove({'uuid': user_data.uuid})
        else:
            web.internalerror("could not write data")
        return web.seeother('/editor')

    def GET(self, uuid=None):
        print uuid, question_global
        question_global['uuid'] = uuid
        print uuid, question_global
        if uuid is not None:
            q = qv_questions.find_one({'uuid': uuid})
            web.header('Content-Type', 'application/json')

            return dumps(q, default=json_util.default)
        else:
            return dumps(None)


class results:

    def compute_results(self, uuid):
        answers = qv_collection.find({'uuid': uuid})

        results = {}
        comments = []
        for answer in answers:
            for (k, v) in answer.items():
                if (v == 'on'):
                    if k not in results:
                        results[k] = 0
                    results[k] += 1
            comments.append(answer['feedback'])

        sorted_keys = results.keys()
        sorted_keys.sort()

        dataset = {
            'label': "result",
            'data': [results[r] for r in sorted_keys]
        }

        data = {
            'labels':   sorted_keys,
            'datasets': [dataset],
            'comments': comments
        }

        return data

    def GET(self, uuid=question_global['uuid']):
        web.header('Content-Type', 'application/json')
        data = self.compute_results(uuid)
        print uuid, data
        return dumps(data)


class view:

    def GET(self, uuid=question_global['uuid']):
        return renderer.view(uuid)
                    # var data = {
                    #     labels: ["January", "February", "March", "April", "May", "June", "July"],
                    #     datasets: [
                    #         {
                    #             label: "My First dataset",
                    #             fillColor: "rgba(220,220,220,0.5)",
                    #             strokeColor: "rgba(220,220,220,0.8)",
                    #             highlightFill: "rgba(220,220,220,0.75)",
                    #             highlightStroke: "rgba(220,220,220,1)",
                    #             data: [65, 59, 80, 81, 56, 55, 40]
                    #         },
                    #         {
                    #             label: "My Second dataset",
                    #             fillColor: "rgba(151,187,205,0.5)",
                    #             strokeColor: "rgba(151,187,205,0.8)",
                    #             highlightFill: "rgba(151,187,205,0.75)",
                    #             highlightStroke: "rgba(151,187,205,1)",
                    #             data: [28, 48, 40, 19, 86, 27, 90]
                    #         }
                    #     ]
                    # };


        #return web.seeother('/')


def signal_handler(signum, frame):
    app.stop()
    print "stopped."


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
