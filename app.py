import sys
import os
abspath = os.path.dirname(__file__)
print abspath

if len(abspath) > 0:
    sys.path.append(abspath)
    os.chdir(abspath)

#from flask import Flask, render_template, request, jsonify, Blueprint

import web
import signal
from json import dumps
from pymongo import MongoClient
from uuid import uuid4
from datetime import datetime
from bson import json_util
from threading import Condition
import httpagentparser
from os import _exit

import time
import config


from urlparse import urlparse

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
    'small':                             # arg1 is the domain
    {'pattern': '/(.+)/small',
     'class': 'small',
     'method': 'get'
     },
    'history':                             # arg1 is the domain
    {'pattern': '/(.+)/history',
     'class': 'history',
     'method': 'get'
     },
    'editor':                           # arg1 is the domain
    {'pattern': '/(.+)/editor',
     'class': 'editor',
     'method': 'get'
     },
    'login':                           # arg1 is the domain, arg2 the admin_url
    {'pattern': '/(.+)/(.+)/login',
     'class': 'login',
     'method': 'get'
     },
    'logoff':                           # arg1 is the domain, arg2 the admin_url
    {'pattern': '/(.+)/(.+)/logout',
     'class': 'logoff',
     'method': 'get'
     },
    # API:
    'user_post':                        # arg1 is the domain (POST only)
    {'pattern': '/api/(.+)/a',
     'class': 'ask_question',
     'method': 'post'
     },
    'answers_post':                     # arg1 is the domain (POST only)
    {'pattern': '/api/(.+)/a/(.+)',    # arg2 is the question UUID
     'class': 'answers',
     'method': 'post'
     },
    'question_post':                    # for POSTs to edit questions
    {'pattern': '/api/(.+)/q',     # (uuid in payload)
     'class': 'questions',              # arg1: domain
     'method': 'post'
     },
    'question_get':                     # for GETs to retrieve question data
    {'pattern': '/api/(.+)/q/(.+)',  # arg1 is domain, arg 2 uuid of question
     'class': 'questions',
     'method': 'get'
     },
    'results_get':                      # arg1 is domain, arg 2 uuid of question
    {'pattern': '/api/(.+)/r/(.+)',
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

# the session UUID is used to determine
# if a client had already submitted an answer

session_uuid = uuid4()
admin_uuid = uuid4()

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

renderer = web.template.render('templates', base="base", globals=globals())


class QuickVoteApp(web.application):
    def run(self, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', config.listen_port))

if __name__ == '__main__':
    app = QuickVoteApp((), globals())
else:
    app = web.application(urls, globals(), autoreload=False)

path_prefix = urlparse(config.base_url).path

for v in urls.values():
    app.add_mapping(v['pattern'], v['class'])
    #v['url_pattern'] = '../'+v['pattern'][1:].replace('(.+)', '%s')
    v['url_pattern'] = path_prefix + v['pattern'][1:].replace('(.+)', '%s')
    print '(%s, %s, %s)' % (v['pattern'], v['class'], v['url_pattern'])


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

    def is_admin(self, domain):
        c = web.cookies().get("quuid_" + domain)
        if c is None:
            return False
        return self.is_valid_admin(domain, c)

    def get_active_question(self, domain):
        c = self.domain_coll.find_one({'name': domain})
        return c['active_question'] if c is not None else None

    def set_active_question(self, domain, uuid):
        global session_uuid
        c = self.domain_coll.find_one({'name': domain})
        if c is None:
            raise RuntimeError('domain %s not in database' % domain)
        c['active_question'] = uuid
        self.domain_coll.save(c)
        session_uuid = self.get_active_session(domain, uuid)

    def set_active_session(self, domain, quuid, suuid=None):
        global session_uuid
        c = self.domain_coll.find_one({'name': domain})
        if c is None:
            raise RuntimeError('domain %s not in database' % domain)
        if 'session' not in c:
            print "NOT IN YET"
            c['session'] = {}
        if suuid is None:
            suuid = str(uuid4())
        c['session'][quuid] = suuid
        session_uuid = suuid
        self.domain_coll.save(c)
        return suuid

    def get_active_session(self, domain, quuid):
        c = self.domain_coll.find_one({'name': domain})
        if 'session' not in c:
            c['session'] = {}

        if quuid not in c['session']:
            return self.set_active_session(domain, quuid)

        return c['session'][quuid]

qv_domains = domain_manager(qv_db)


### Renderers for actual interface:
class ask_question:

    def GET(self, domain):
        uuid = qv_domains.get_active_question(domain)
        qs = qv_questions.find_one({'uuid': uuid})
        if qs is None:
        	return "<html><body><H1>no question available at the moment</H1></body></html>"
        if 'image' not in qs:
            qs['image'] = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
        data = {'qs': qs,
                'session_uuid': session_uuid,
                'submit_url': urls['user_post']['url_pattern'] % domain,
                }
        return renderer.index(data)

    def POST(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        c = web.cookies(session_uuid=uuid4()).session_uuid
        if str(c) == str(session_uuid):
            print "user submitted again to same session"
            return renderer.duplicate(urls['user']['url_pattern']
                                      .replace('$', '') % domain)
        else:
            web.setcookie('session_uuid', session_uuid, 3600)

        data = {}
        data.update(web.input())
        data['env'] = {}
        for (k, v) in web.ctx.env.items():
            if type(v) is str:
                data['env'][k.replace('.', '_')] = v
        data['inserted_at'] = datetime.now()
        data['session'] = qv_domains.get_active_session(domain,
                                                        data['uuid'])
        new_input.acquire()
        try:
            qv_collection.insert(data)
            new_input.notifyAll()
        finally:
            new_input.release()
        return renderer.submit(urls['user']['url_pattern']
                               .replace('$', '') % domain)


class login:

    def GET(self, domain, admin_url):
        if not qv_domains.is_valid_admin(domain, admin_url):
            return web.notacceptable()
        web.setcookie("quuid_"+domain, admin_url)
        return web.ok()


class logoff:

    def GET(self, domain, admin_url):
        if not qv_domains.is_valid_admin(domain, admin_url):
            return web.notacceptable()
        web.setcookie("quuid_"+domain, admin_url, expires=-1)
        return web.ok()


class editor:

    def GET(self, domain):
        if not qv_domains.is_admin(domain):
            return web.notacceptable()
        qs = qv_questions.find({'domain': domain}).sort([('inserted_at', -1)])

        data = {
            'existing_questions': [],
            'new_uuid': uuid4(),
            'domain': domain,
            'active_question': qv_domains.get_active_question(domain),
            'submit_url': urls['question_post']['url_pattern']
            % (domain),
            'get_url': urls['question_get']['url_pattern'] % (domain, ''),
            'get_results_url': urls['results_get']['url_pattern']
            % (domain, ''),
            'delete_url': urls['answers_post']['url_pattern'] % (domain, ''),
            'results_url': urls['view']['url_pattern'] % (domain),
            'history_url': urls['history']['url_pattern'] % (domain),
        }

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.editor(data)


class admin:

    def GET(self, domain):
        if not qv_domains.is_admin(domain):
            return web.notacceptable()
        qs = qv_questions.find({'domain': domain}).sort([('inserted_at', -1)])

        data = {
            'existing_questions': [],
            'new_uuid': uuid4(),
            'domain': domain,
            'active_question': qv_domains.get_active_question(domain),
            'submit_url': urls['question_post']['url_pattern']
            % (domain),
            'get_url': urls['question_get']['url_pattern'] % (domain, ''),
            'get_results_url': urls['results_get']['url_pattern']
            % (domain, ''),
            'delete_url': urls['answers_post']['url_pattern'] % (domain, ''),
            'results_url': urls['view']['url_pattern'] % (domain),
            'history_url': urls['history']['url_pattern'] % (domain),
        }

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.admin(data)


class view:

    def GET(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        if not qv_domains.is_admin(domain):
            return web.notacceptable()

        uuid = qv_domains.get_active_question(domain)
        data = {
            'uuid': uuid,
            'domain': domain,
            'vote_url': config.base_url+domain+'/',
            'get_url': urls['results_get']['url_pattern'] % (domain, uuid),
            'existing_questions': [],
            'active_question': qv_domains.get_active_question(domain),
            'activate_question_url': urls['question_get']['url_pattern']
            % (domain, ''),
            'delete_url': urls['answers_post']['url_pattern'] % (domain, ''),
            'get_results_url': urls['results_get']['url_pattern']
            % (domain, ''),
            'history_url': urls['history']['url_pattern'] % (domain),
        }

        qs = qv_questions.find({'domain': domain}).sort([('inserted_at', -1)])

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.view(data)


class small:

    def GET(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        if not qv_domains.is_admin(domain):
            return web.notacceptable()

        uuid = qv_domains.get_active_question(domain)
        data = {
            'uuid': uuid,
            'domain': domain,
            'vote_url': config.base_url+domain+'/',
            'get_url': urls['results_get']['url_pattern'] % (domain, uuid)
        }

        return renderer.small(data)


class history:

    def GET(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        if not qv_domains.is_admin(domain):
            return web.notacceptable()

        uuid = qv_domains.get_active_question(domain)
        data = {
            'uuid': uuid,
            'domain': domain,
            'vote_url': config.base_url+domain+'/',
            'get_url': urls['results_get']['url_pattern'] % (domain, uuid)
        }

        return renderer.history(data)



## API access points
class answers:

    def POST(self, domain, question):
        if not qv_domains.is_admin(domain):
            return web.notacceptable()
        qv_domains.set_active_session(domain, question)
        #qv_collection.remove({'uuid': question, 'domain': domain})
        return web.ok()


class questions:

    def POST(self, domain):
        if not qv_domains.is_admin(domain):
            return web.notacceptable()

        user_data = web.input()

        if hasattr(user_data, "delete_question") and \
            hasattr(user_data, 'uuid'):

            print("Deleting")
            qv_questions.remove({'uuid': user_data.uuid})
            
        elif hasattr(user_data, 'options') and \
           hasattr(user_data, 'correct') and \
           hasattr(user_data, 'question') and \
           hasattr(user_data, 'domain') and \
           hasattr(user_data, 'uuid'):
            if user_data.uuid == '':
                user_data.uuid = str(uuid4())
            if user_data.domain == '':
                user_data.domain = str(domain)
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
            if hasattr(user_data, 'image'):
                doc['image'] = user_data.image
            # the is a delete request if the question is empty:
            if len(user_data.question) > 0:
                qv_questions.update({'uuid': user_data.uuid},
                                    doc, upsert=True)
            else:
                qv_questions.remove({'uuid': user_data.uuid})
        else:
            web.internalerror("could not all data provided as required: "
                              "user_data=%s" % user_data)
        return web.ok()  # web.seeother('/%s/%s/editor' % (domain, admin_url))

    def GET(self, domain, uuid):
        q = qv_questions.find_one({'uuid': uuid})
        i = web.input()
        if q is not None:
            if "activate" in i:
                print "set active question for %s to %s" % (domain, uuid)
                qv_domains.set_active_question(domain, uuid)
            web.header('Content-Type', 'application/json')
            return dumps(q, default=json_util.default)
        else:
            return web.notfound()


class results:

    def generate_user_results(self, user_agents):
        try:
            sorted_keys = user_agents.keys()
            sorted_keys.sort()
            dataset = {
                'label': "user agents",
                'fillColor': "rgba(0,0,120,0.5)",
                'data': [user_agents[r] for r in sorted_keys]
            }
            data = {
                'labels':   sorted_keys,
                'datasets': [dataset],
            }
        except Exception as e:
            print e
            pass

        return data

    def compute_results(self, domain, uuid, session=None):
        if session is None:
            session = qv_domains.get_active_session(domain, uuid)
        answers = qv_collection.find({'uuid': uuid, 'session': session})
        question = qv_questions.find_one({'uuid': uuid})

        results = {}
        comments = []
        sorted_keys = []
        if question is not None:

            total_submissions = 0.0
            total_correct_submissions = 0.0
            tp = 0.0
            tn = 0.0
            fp = 0.0
            fn = 0.0

            user_agents = {}

            for answer in answers:

                try:
                    if 'env' in answer:
                        if 'HTTP_USER_AGENT' in answer['env']:
                            ua = httpagentparser.detect(answer['env']['HTTP_USER_AGENT'])
                            try:
                                k = ua['platform']['name']  #+ " / " + ua['browser']['name']
                            except:
                                k = "*unknown* / " + ua['browser']['name']
                            if k not in user_agents:
                                user_agents[k] = 0
                            user_agents[k] += 1
                except Exception as ex:
                    print "couldn't work with HTTP_USER_AGENT: %s %s" % (ex, answer['env']['HTTP_USER_AGENT'])
                    print ua
                    pass

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
                if len(answer['feedback']) > 0:
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

            try:
                sensitivity = tp / (tp + fn)
            except:
                sensitivity = 1

            try:
                specificity = tn / (tn + fp)
            except:
                specificity = 1
            try:
                accuracy = (tp + tn) / (tp + tn + fp + fn)
            except:
                accuracy = 1
            try:
                corrects_ratio = float(total_correct_submissions) / total_submissions
            except:
                corrects_ratio = 1

            data = {
                'userChart': self.generate_user_results(user_agents),
                'labels':   sorted_keys,
                'datasets': [dataset, dataset_c],
                'comments': comments,
                'totals': total_submissions,
                'corrects': total_correct_submissions,
                'raw_stats': {
                    'percent': corrects_ratio,
                    'sensitivity': sensitivity,
                    'specificity': specificity,
                    'accuracy': accuracy
                },
                'percent': "%2.1f%%"
                % (corrects_ratio * 100.0),
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

    def response(self, data):
        response = "data: " + data + "\n\n"
        return response

    def GET(self, domain, uuid):
        w = web.input()
        mode = 'stream'
        if 'mode' in w:
            mode = w['mode']

        method_name = 'GET_' + str(mode)
        # Get the method from 'self'. Default to a lambda.
        method = getattr(self, method_name, self.GET_stream)
        print method
        # Call the method as we return it
        return method(domain, uuid)

    def GET_stream(self, domain, uuid):
        block = False
        web.header("Content-Type", "text/event-stream")
        web.header('Cache-Control', 'no-cache')
        web.header('Content-length:', 1000)
        while True:
            new_input.acquire()
            try:
                if block:
                    new_input.wait(timeout=30)
            finally:
                new_input.release()
            block = True
            #time.sleep(1);
            data = self.compute_results(domain, uuid)
            data['dummy'] = config.dummy_data

            r = self.response(dumps(data))
            yield r

    def GET_history(self, domain, uuid):
        web.header('Content-Type', 'application/json')
        sessions = qv_collection.find({'uuid': uuid}).distinct('session')
        results = {}
        last_inserted = {}
        for s in sessions:
            answers = qv_collection.find({'session': s,
                                          'uuid': uuid})\
                .sort([('inserted_at', -1)])
            last_inserted[s] = answers[0]['inserted_at']
            results[s] = self.compute_results(domain, uuid, s)

        # sort according to time
        decorated = [(last_inserted[s], s) for s in sessions]
        decorated.sort()
        sessions = [s for l, s in decorated]

        totals_data = []
        corrects_data = []
        accuracy_data = []
        for s in sessions:
            totals_data.append(results[s]['totals'])
            accuracy_data.append(100.0 * results[s]['raw_stats']['accuracy'])
            corrects_data.append(100.0 * results[s]['corrects'] / (
                float(results[s]['totals']))
            )

        max_totals = float(max(totals_data))
        totals_data = [100.0 * x / max_totals for x in totals_data]

        dataset_totals = {
            'label': 'Participation %',
            'fillColor': "rgba(0,0,220,0.3)",
            'strokeColor': "rgba(0,0,220,1)",
            'pointColor': "rgba(0,0,220,1)",
            'pointStrokeColor': "#fff",
            'pointHighlightFill': "#fff",
            'pointHighlightStroke': "rgba(220,220,220,1)",
            'data': totals_data
        }

        dataset_corrects = {
            'label': 'Correct %',
            'fillColor': "rgba(0,220,0,0.3)",
            'strokeColor': "rgba(0,220,0,1)",
            'pointColor': "rgba(0,220,0,1)",
            'pointStrokeColor': "#fff",
            'pointHighlightFill': "#fff",
            'pointHighlightStroke': "rgba(220,220,220,1)",
            'data': corrects_data
        }

        dataset_accuracy = {
            'label': 'Accuracy % ',
            'fillColor': "rgba(220,220,0,0.5)",
            'strokeColor': "rgba(220,220,0,1)",
            'pointColor': "rgba(220,220,0,1)",
            'pointStrokeColor': "#fff",
            'pointHighlightFill': "#fff",
            'pointHighlightStroke': "rgba(220,220,220,1)",
            'data': accuracy_data
        }


        data = {
            'question': results[sessions[0]]['question'],
            'labels': [str(last_inserted[s].date()) for s in sessions],
            'datasets': [dataset_totals, dataset_corrects, dataset_accuracy]
        }

        # dataset = {
        #     'label': "responses",
        #     'fillColor': "rgba(120,0,0,0.5)",
        #     'data': [results[r] for r in sorted_keys]
        # }

        return dumps(data, default=json_util.default)



def signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
else:
    application = app.wsgifunc()
