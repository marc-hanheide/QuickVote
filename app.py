#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps
from pymongo import MongoClient
from uuid import uuid4
from datetime import datetime
from bson import json_util

import config

urls = {
    'user':                             # arg1 is the domain (questionnaire)
    {'pattern': '/(.+)/$',
     'class': 'ask_question',
     'method': 'get'
     },
    'view':                             # arg1 is the domain
    {'pattern': '/(.+)/view',
     'class': 'view',
     'method': 'get'
     },
    'editor':                           # arg1 is the domain, arg2 the admin_url
    {'pattern': '/(.+)/(.+)/editor',
     'class': 'editor',
     'method': 'get'
     },
    # API:
    'user_post':                        # arg1 is the domain (POST only)
    {'pattern': '/api/(.+)/a',
     'class': 'ask_question',
     'method': 'post'
     },
    'question_post':                    # for POSTs to edit questions
    {'pattern': '/api/(.+)/(.+)/q',     # (uuid in payload)
     'class': 'questions',              # arg1: domain, arg2: admin_url
     'method': 'post'
     },
    'question_get':                     # for GETs to retrieve question data
    {'pattern': '/api/(.+)/q/(.+)',     # arg1 is domain, arg 2 uuid of question
     'class': 'questions',
     'method': 'get'
     },
    'results_get':                      # GET: arg1 is uuid of the question
    {'pattern': '/api/r/(.+)',
     'class': 'results',
     'method': 'get'
     }
}


# urls = (
#     '/(.+)/', 'ask_question',           # arg1 is the domain (questionnaire)
#     '/(.+)/view', 'view',               # arg1 is the domain
#                                        #(returns results for current question)
#     '/(.+)/(.+)/editor', 'editor',    # arg1 is the domain, arg2 the admin_url

#     # The following are API access points
#     '/api/(.+)/(.+)/q', 'questions',    # for POSTs to edit questions
#                                         # (uuid in payload)
#                                         # arg1: domain, arg2: admin_url
#     '/api/q/(.+)', 'questions',         # for GETs to retrieve question data
#                                         # arg1 is uuid of question
#     '/api/r/(.+)', 'results',           # GET: arg1 is uuid of the question
#     '/api/(.+)/a', 'ask_question',      # arg1 is the domain (POST only)
# )

# question_global = {
#     'uuid': uuid4(),
#     'question': "What is the meaning of live?",
#     'answers': ['A', 'B', 'C', 'D'],
#     'correct': ['A, B']
# }


client = MongoClient(config.mongo_host, config.mongo_port)

qv_db = client['QuickVote']

qv_collection = qv_db['answers']
qv_collection.create_index('uuid')
qv_collection.create_index('domain')
qv_collection.create_index('inserted_at')

qv_questions = qv_db['questions']
qv_questions.create_index('uuid', unique=True)
qv_questions.create_index('domain')

renderer = web.template.render('templates', base="base", globals=globals())


class QuickVoteApp(web.application):
    def run(self, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', config.listen_port))


app = QuickVoteApp((), globals())

for v in urls.values():
    app.add_mapping(v['pattern'], v['class'])
    v['url_pattern'] = v['pattern'].replace('(.+)', '%s')
    print '(%s, %s)' % (v['pattern'], v['class'])


class domain_manager:

    def __init__(self, db):
        self.domain_coll = db['domains']
        self.ensure_debug_domain()
        self.domain_coll.create_index('name', unique=True)
        self.domain_coll.create_index('admin_url', unique=True)


    def ensure_debug_domain(self):
        # ensure testdomain
        if self.domain_coll.find_one({'name': 'debug'}) is None:
            self.domain_coll.insert(
                {
                    'name': 'debug',
                    'inserted_at': datetime.now(),
                    'admin_url': str(uuid4()),
                    'active_question': None
                }
            )

    def get_name_from_admin_url(self, admin_url):
        c = self.domain_coll.find_one({'admin_url': admin_url})
        return c['name'] if c is not None else None

    def is_valid_admin(self, domain, admin_url):
        true_name = self.get_name_from_admin_url(admin_url)
        return true_name == domain

    def get_active_question(self, domain):
        c = self.domain_coll.find_one({'name': domain})
        return c['active_question'] if c is not None else None

    def set_active_question(self, domain, uuid):
        c = self.domain_coll.find_one({'name': domain})
        if c is None:
            raise RuntimeError('domain %s not in database' % domain)
        c['active_question'] = uuid
        self.domain_coll.save(c)


qv_domains = domain_manager(qv_db)


### Renderers for actual interface:
class ask_question:
    def GET(self, domain):
        uuid = qv_domains.get_active_question(domain)
        qs = qv_questions.find_one({'uuid': uuid})
        data = {'qs': qs,
                'submit_url': urls['user_post']['url_pattern'] % domain,
                }
        return renderer.index(data)

    def POST(self, domain):
        data = {}
        data.update(web.input())
        data['env'] = {}
        for (k, v) in web.ctx.env.items():
            if type(v) is str:
                data['env'][k.replace('.','_')] = v
        data['inserted_at'] = datetime.now()
        qv_collection.insert_one(data)
        return renderer.submit(domain)


class editor:

    def GET(self, domain, admin_url):
        if not qv_domains.is_valid_admin(domain, admin_url):
            return web.notacceptable()
        qs = qv_questions.find({'domain': domain}).sort([('inserted_at', -1)])

        data = {
            'existing_questions': [],
            'new_uuid': uuid4(),
            'domain': domain,
            'submit_url': urls['question_post']['url_pattern']
            % (domain, admin_url),
            'get_url': urls['question_get']['url_pattern'] % (domain, ''),
            'results_url': urls['view']['url_pattern'] % (domain),
        }

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.editor(data)


class view:

    def GET(self, domain):
        uuid = qv_domains.get_active_question(domain)
        data = {
            'uuid': uuid,
            'domain': domain,
            'get_url': urls['results_get']['url_pattern'] % (uuid)
        }
        return renderer.view(data)


## API access points

class questions:

    def POST(self, domain, admin_url):
        if not qv_domains.is_valid_admin(domain, admin_url):
            return web.notacceptable()

        user_data = web.input()
        if hasattr(user_data, 'options') and \
           hasattr(user_data, 'correct') and \
           hasattr(user_data, 'question') and \
           hasattr(user_data, 'domain') and \
           hasattr(user_data, 'uuid'):
            options_str = user_data.options.split(',')
            correct_str = user_data.correct.split(',')
            doc = {
                'options': [o.strip() for o in options_str],
                'correct': [o.strip() for o in correct_str],
                'question': user_data.question,
                'uuid': user_data.uuid,
                'domain': user_data.domain,
                'inserted_at': datetime.now()
            }
            # the is a delete request if the question is empty:
            if len(user_data.question) > 0:
                qv_questions.replace_one({'uuid': user_data.uuid},
                                         doc, upsert=True)
            else:
                qv_questions.remove({'uuid': user_data.uuid})
        else:
            web.internalerror("could not all data provided as required: "
                              "user_data=%s" % user_data)
        return web.seeother('/%s/%s/editor' % (domain, admin_url))

    def GET(self, domain, uuid):
        q = qv_questions.find_one({'uuid': uuid})
        if q is not None:
            qv_domains.set_active_question(domain, uuid)
            web.header('Content-Type', 'application/json')
            return dumps(q, default=json_util.default)
        else:
            return web.notfound()


class results:

    def compute_results(self, uuid):
        answers = qv_collection.find({'uuid': uuid})
        question = qv_questions.find_one({'uuid': uuid})

        results = {}
        comments = []
        sorted_keys = []
        if question is not None:

            total_submissions = 0
            total_correct_submissions = 0
            tp = 1.0
            tn = 1.0
            fp = 1.0
            fn = 1.0

            for answer in answers:
                correct = True
                for opt in question['options']:
                    if opt not in results:
                        results[opt] = 0
                    if opt in answer:
                        results[opt] += 1
                        if opt in question['correct']:
                            tp += 1
                        else:
                            fp += 1
                            correct = False
                    else:
                        if opt in question['correct']:
                            correct = False
                            fn += 1
                        else:
                            tn += 1

                total_correct_submissions += 1 if correct else 0
                total_submissions += 1
                comments.append(answer['feedback'])

            sorted_keys = results.keys()
            sorted_keys.sort()

            dataset = {
                'label': "responses",
                'fillColor': "rgba(120,0,0,0.5)",
                'data': [results[r] for r in sorted_keys]
            }

            # correct_data = []
            # for r in sorted_keys:
            #     if r in correct:
            #         correct_data.append(total_submissions)
            #     else:
            #         correct_data.append(0)

            dataset_c = {
                'label': "correct",
                'fillColor': "rgba(0,100,0,0.5)",
                'data': [(total_submissions
                if r in question['correct'] else 0) for r in sorted_keys]
            }

            print total_submissions, total_correct_submissions, dataset_c

            sensitivity = tp / (tp + fn)
            specificity = tn / (tn + fp)
            accuracy = (tp + tn) / (tp + tn + fp + fn)

            data = {
                'labels':   sorted_keys,
                'datasets': [dataset, dataset_c],
                'comments': comments,
                'totals': total_submissions,
                'corrects': total_correct_submissions,
                'percent': "%2.1f%%"
                % (total_correct_submissions * 100.0 / total_submissions),
                'sensitivity': "%2.1f%%"
                % (sensitivity * 100.0),
                'specificity': "%2.1f%%"
                % (specificity * 100.0),
                'accuracy': "%2.1f%%"
                % (accuracy * 100.0),
                'question': question['question']
                if question is not None
                else '*unknown*'
            }

            return data
        else:
            raise web.NotFound('error getting data')

    def GET(self, uuid):
        web.header('Content-Type', 'application/json')
        data = self.compute_results(uuid)
        print uuid, data
        return dumps(data)


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
