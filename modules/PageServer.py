from common import *
from domains import qv_domains
from logins import logman
from logins import usrman
from logins import qv_logins
import glob
from random import randint
from collections import defaultdict
from hashlib import md5

class ask_question:

    def GET(self, domain):
        user_uuid = web.cookies().get('qv_user_uuid')
        domain_session_uuid_cookie = web.cookies().get(
            'qv_domain_session_uuid')
        domain_session_uuid = qv_domains.get_domain_session(domain)
        qv_domains.DomainActive(domain)

        if user_uuid is None:
            print 'new user'
            web.setcookie('qv_user_uuid', str(uuid4()))
        if domain_session_uuid_cookie is None or \
           domain_session_uuid != domain_session_uuid_cookie:
            n_group = qv_domains.get_n_groups(domain)

            print n_group, domain_session_uuid, domain_session_uuid_cookie
            if n_group > 0:
                group = randint(1, n_group)
            else:
                group = 0
            web.setcookie('qv_user_group', str(group))
            web.setcookie('qv_domain_session_uuid', str(domain_session_uuid))

            return renderer.start(config.base_url,
                                  domain,
                                  logman.LoggedIn())
        else:
            user_group = web.cookies(
                qv_user_group='').qv_user_group

            uuid = qv_domains.get_active_question(domain)
            qs = qv_questions.find_one({'uuid': uuid})
            if qs is not None and 'image' not in qs:
                qs['image'] = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
            data = {
                    'user_group': user_group,
                    'qs': qs,
                    'session_uuid': glob.session_uuid,
                    'submit_url': glob.urls['user_post']['url_pattern']
                    % domain,
                    }
            return renderer.index(config.base_url, data,
                                  logman.LoggedIn())

    def POST(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        c = web.cookies(session_uuid=uuid4()).session_uuid
        if str(c) == str(glob.session_uuid):
            print "user submitted again to same session"
            return renderer.duplicate(config.base_url,
                                      glob.urls['user']['url_pattern']
                                      .replace('$', '') % domain,
                                      logman.LoggedIn())
        else:
            web.setcookie('session_uuid', glob.session_uuid, 3600)

        user_group = web.cookies(
            qv_user_group='').qv_user_group

        data = {}
        data.update(web.input())
        data['env'] = {}
        for (k, v) in web.ctx.env.items():
            if type(v) is str:
                data['env'][k.replace('.', '_')] = v
        data['inserted_at'] = datetime.now()
        data['user_group'] = user_group
        data['session'] = qv_domains.get_active_session(domain,
                                                        data['uuid'])
        new_input.acquire()
        try:
            qv_collection.insert(data)
            new_input.notifyAll()
        finally:
            new_input.release()
        return renderer.submit(config.base_url,
                               glob.urls['user']['url_pattern']
                               .replace('$', '') % domain, logman.LoggedIn())


class mainlogin:
    def GET(self):
        if logman.LoggedIn():
            logman.Logout()
        return renderer.mainlogin(config.base_url,
                                  logman.LoggedIn())

    def POST(self):
        var = web.input()

        # check for alphanumeric inputs for username
        if var['Username'].isalnum() == False:
            if var['Username'].isalpha() == False:
                if var['Username'].isdigit() == False:
                    return "Username is invalid! Use only Letters and Digits e.g. Derek123"

        # look for username within login collection
        record = qv_logins.find_one({'Username': var['Username']})
        if record is None:
            return "User does not exist!"

        # hash submited password and compare to record
        if record['Password'].encode("utf-8") == hmac.new('QVkey123',
                                                          var['Password'],
                                                          hashlib.sha512).hexdigest():

            # create login session, redirect if success
            if logman.Login(var['Username']):
                # send user to index page
                return "Success"
        else:
            return "Username or Password is Incorrect!"


class Users:
    def GET(self):
        if logman.isAdmin():
            return renderer.users(config.base_url, True, usrman.get_usr_list())
        return web.notacceptable()

    def POST(self):
        w = web.input()
        if w["action"] == "MUA":
            if w["usr"] != None:
                if usrman.make_user_admin(w["usr"]):
                    return "Success"
        if w["action"] == "RUA":
            if w["usr"] != None:
                if usrman.revoke_user_admin(w["usr"]):
                    return "Success"
        if w["action"] == "CU":
            if w["usr"] != None and w["passw"] != None and w["admin"]:
                a = False
                if w["admin"] == "T":
                    a = True
                if usrman.create_user(w["usr"],w["passw"],a):
                    return "Success"
        if w["action"] == "CP":
            if w["usr"] != None and w["passw"] != None:
                if usrman.change_user_password(w["usr"],w["passw"]):
                    return "Success"
        if w["action"] == "DU":
            if w["usr"] != None:
                if usrman.delete_user(w["usr"]):
                    return "Success"
        return "Fail"

class home:
    def GET(self):
        # get list of domain names
        domain_list = qv_domains.get_list_of_domains()
        if logman.LoggedIn():
            if logman.isAdmin():
                return renderer.home(config.base_url,domain_list,domain_list,True,True) # (domain info, loggedin, isAdmin)
            manage_domain_list = []
            for d in domain_list:
                if qv_domains.Access_domain(d[0],web.cookies().get('QV_Usr')) == "Coord" or qv_domains.Access_domain(d[0],web.cookies().get('QV_Usr')) == "Editor":
                    manage_domain_list.append([d[0],d[1],d[2],qv_domains.Access_domain(d[0],web.cookies().get('QV_Usr'))])
            return renderer.home(config.base_url,domain_list,manage_domain_list,True,False) # (domain info, loggedin, isAdmin)
        return renderer.home(config.base_url,domain_list,None,False,False)

class EditDom:
    # function to add / remove / edit a domain
    def POST(self,action,domain):
        if logman.isAdmin():
            # add domain
            if action == "Add":
                # insert new domain
                qv_domains.domain_coll.insert(
                    {
                        'name': domain,
                        'inserted_at': datetime.now(),
                        'lastActive': datetime.now(),
                        'lastEdited': datetime.now(),
                        'lastEditedBy': "N/A",
                        'admin_url': str(uuid4()),
                        'active_question': None,
                        'users' : []
                    }
                )
                print "created" + domain
                return "success"
            if action == "Remove":
                qv_domains.domain_coll.delete_one({'name': domain})
                print "deleted " + domain
                return "success"
            if action == "Update":
                rec = qv_domains.domain_coll.find_one({'name': domain})
                rec["name"] = domain
                print "changed name to " + domain
                return "success"
        return "failed"


class manage:
    def POST(self, domain):
        w = web.input()
        n = w['team_size']
        qv_domains.set_n_groups(domain, n)
        qv_domains.set_domain_session(domain, uuid4())

        return web.ok()

    def GET(self,domain):
        if logman.LoggedIn() == True:
            if qv_domains.is_domain(domain):
                n_group = qv_domains.get_n_groups(domain)

                recs = usrman.get_usr_list()
                usrs = []
                for r in recs:
                    usrs.append(r["Username"])
                if qv_domains.Access_domain(domain,web.cookies().get('QV_Usr')) == "Coord":
                    return renderer.manage(config.base_url,
                        domain,                                                         # name of domain to manage (string)
                        True,                                                           # is user logged in? (boolean)
                        logman.isAdmin(),                                               # is user and Admin? (boolean)
                        "Coord",                                                        # Access that user has to domain (string)
                        qv_domains.get_list_of_editors(domain),                         # list of editors for domain (string[] / None)
                        None,                                                           # list of coordinators for domain (string[] / None)
                        usrs,
                        n_group,
                        config.base_url +
                        domain +
                        '/view?magic=' + qv_domains.get_admin_url(domain)

                    )
                if logman.isAdmin():
                    return renderer.manage(config.base_url,
                        domain,                                                         # name of domain to manage (string)
                        True,                                                           # is user logged in? (boolean)
                        logman.isAdmin(),                                               # is user and Admin? (boolean)
                        None,                                                           # Access that user has to domain (string)
                        qv_domains.get_list_of_users(domain),                           # list of users for domain (string[[]] / None)
                        None,                                                           # list of coordinators for domain (string[] / None)
                        usrs,
                        n_group,
                        config.base_url +
                        domain +
                        '/view?magic=' + qv_domains.get_admin_url(domain)
                    )
                if qv_domains.Access_domain(domain,web.cookies().get('QV_Usr')) == "Editor":
                    return renderer.manage(config.base_url,
                        domain,                                                         # name of domain to manage (string)
                        True,                                                           # is user logged in? (boolean)
                        logman.isAdmin(),                                               # is user and Admin? (boolean)
                        "Editor",                                                       # Access that user has to domain (string)
                        [""],                                                           # list of editors for domain (string[] / None)
                        None,                                                           # list of coordinators for domain (string[] / None)
                        usrs,
                        n_group
                    )
            else:
                return web.notfound()
        return web.seeother('/login')
class MainageDomainUsers:
    def POST(self,domain):

        data = web.input()
        if logman.LoggedIn():
            # update editors in list
            if qv_domains.Access_domain(domain,web.cookies().get('QV_Usr')) == "Coord":
                if qv_domains.update_list_of_editors(domain,data):
                    return "Successful!"
            if logman.isAdmin():
                if qv_domains.update_list_of_all(domain,data):
                    return "Admin Successful!"
            return "Failed! You are not logged in!"

class editor:

    def GET(self, domain):

        # check logged in
        if not logman.LoggedIn():
            print "Failed Login!"
            return web.seeother('/login')

        # check for valid domain
        if not qv_domains.is_domain(domain):
            print "Failed domain check!"
            return web.notacceptable()

        # check that user has access to this domain
        attempt_at_access = qv_domains.Access_domain(domain,web.cookies().get('QV_Usr'))
        if logman.isAdmin() or attempt_at_access == "Coord" or attempt_at_access == "Editor":
            print "Authourized"
        else:
            print "Failed Access!"
            return web.notacceptable()


        qs = qv_questions.find({'domain': domain}).sort([('inserted_at', -1)])

        data = {
            'existing_questions': [],
            'new_uuid': uuid4(),
            'domain': domain,
            'active_question': qv_domains.get_active_question(domain),
            'submit_url': glob.urls['question_post']['url_pattern']
            % (domain),
            'get_url': glob.urls['question_get']['url_pattern'] % (domain, ''),
            'get_results_url': glob.urls['results_get']['url_pattern']
            % (domain, ''),
            'delete_url': glob.urls['answers_post']['url_pattern'] % (domain, ''),
            'results_url': glob.urls['view']['url_pattern'] % (domain),
            'history_url': glob.urls['history']['url_pattern'] % (domain),
        }

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.editor(config.base_url,data,logman.LoggedIn())


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
            'submit_url': glob.urls['question_post']['url_pattern']
            % (domain),
            'get_url': glob.urls['question_get']['url_pattern'] % (domain, ''),
            'get_results_url': glob.urls['results_get']['url_pattern']
            % (domain, ''),
            'delete_url': glob.urls['answers_post']['url_pattern'] % (domain, ''),
            'results_url': glob.urls['view']['url_pattern'] % (domain),
            'history_url': glob.urls['history']['url_pattern'] % (domain),
        }

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.admin(config.base_url,data,logman.LoggedIn())


class view:

    def GET(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        if not logman.DomainLogin(domain):
            user_data = web.input()
            print qv_domains.get_admin_url(domain)
            if hasattr(user_data, "magic"):
                if user_data.magic == qv_domains.get_admin_url(domain):
                    pass
                else:
                    return web.notacceptable()
            else:
                return web.notacceptable()

        uuid = qv_domains.get_active_question(domain)
        data = {
            'uuid': uuid,
            'domain': domain,
            'vote_url': config.base_url+domain+'/',
            'get_url': glob.urls['results_get']['url_pattern'] % (domain, uuid),
            'existing_questions': [],
            'active_question': uuid,
            'activate_question_url': glob.urls['question_get']['url_pattern']
            % (domain, ''),
            'delete_url': glob.urls['answers_post']['url_pattern'] % (domain, ''),
            'get_results_url': glob.urls['results_get']['url_pattern']
            % (domain, ''),
            'history_url': glob.urls['history']['url_pattern'] % (domain)
        }

        qs = qv_questions.find({'domain': domain}).sort([('inserted_at', -1)])

        qsd = [q for q in qs]

        data['existing_questions'] = qsd

        return renderer.view(config.base_url,data,logman.LoggedIn())


class history:

    def GET(self, domain):
        # verify the cookie is not set to the current session.
        # in that case it would be a resubmission
        if not logman.DomainLogin(domain):
            return web.notacceptable()


        uuid = qv_domains.get_active_question(domain)
        data = {
            'uuid': uuid,
            'domain': domain,
            'vote_url': config.base_url+domain+'/',
            'get_url': glob.urls['results_get']['url_pattern'] % (domain, uuid)
        }

        return renderer.history(config.base_url,data,logman.LoggedIn())

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
            'get_url': glob.urls['results_get']['url_pattern'] % (domain, uuid)
        }

        return renderer.small(config.base_url,data,logman.LoggedIn())

## API access points
class answers:

    def POST(self, domain, question):
        if not logman.DomainLogin(domain):
            return web.notacceptable()
        qv_domains.set_active_session(domain, question)
        return web.ok()

class questions:

    def POST(self, domain):
        if not logman.DomainLogin(domain):
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
        return web.ok()

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

    def generate_group_results(self, group_correct_ratio, group_size_ratio):
        try:
            sorted_keys = group_correct_ratio.keys()
            sorted_keys.sort()
            dataset_corrects = {
                'label': "Group Correctness",
                'fillColor': "rgba(0,120,0,0.5)",
                'data': [group_correct_ratio[r] for r in sorted_keys]
            }
            dataset_size = {
                'label': "Group Size",
                'fillColor': "rgba(100,100,120,0.5)",
                'data': [group_size_ratio[r] for r in sorted_keys]
            }
            data = {
                'labels':   sorted_keys,
                'datasets': [dataset_size, dataset_corrects],
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
            gtp = defaultdict(float)
            gtn = defaultdict(float)
            gfp = defaultdict(float)
            gfn = defaultdict(float)
            group_total_correct_submissions = defaultdict(float)
            group_total_submissions = defaultdict(float)

            user_agents = {}

            for answer in answers:

                try:
                    if 'env' in answer:
                        if 'HTTP_USER_AGENT' in answer['env']:
                            ua = httpagentparser.detect(answer['env']['HTTP_USER_AGENT'])
                            try:
                                k = ua['platform']['name']
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
                if 'user_group' in answer:
                    group = answer['user_group']
                else:
                    group = 0

                for opt in question['options']:
                    if opt not in results:
                        results[opt] = 0
                    if opt in answer:
                        results[opt] += 1
                        if opt in question['correct']:
                            tp += 1
                            gtp[group] += 1
                        else:
                            fp += 1
                            gfp[group] += 1
                            correct = False
                    else:
                        if opt in question['correct']:
                            correct = False
                            fn += 1
                            gfn[group] += 1
                        else:
                            tn += 1
                            gtn[group] += 1

                total_correct_submissions += 1 if correct else 0
                total_submissions += 1
                group_total_correct_submissions[group] += 1 if correct else 0
                group_total_submissions[group] += 1
                if len(answer['feedback']) > 0:
                    comments.append(answer['feedback'])

            sorted_keys = results.keys()
            sorted_keys.sort()

            dataset = {
                'label': "responses",
                'fillColor': "rgba(120,0,0,0.5)",
                'data': [results[r] for r in sorted_keys]
            }

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

            group_correct_ratio = defaultdict(float)
            group_size_ratio = defaultdict(float)
            for g in group_total_submissions:
                group_correct_ratio[g] = group_total_correct_submissions[g] /\
                    group_total_submissions[g]
                group_size_ratio[g] = group_total_submissions[g] /\
                    total_submissions

            data = {
                # 'userChart': self.generate_user_results(user_agents),
                'userChart': self.generate_group_results(group_correct_ratio,
                                                         group_size_ratio),
                'labels':   sorted_keys,
                'datasets': [dataset, dataset_c],
                'comments': comments,
                'totals': total_submissions,
                'corrects': total_correct_submissions,
                'raw_stats': {
                    'percent': corrects_ratio,
                    'sensitivity': sensitivity,
                    'specificity': specificity,
                    'accuracy': accuracy,
                    'group_correct': group_correct_ratio,
                    'group_size_ratio': group_size_ratio
                },
                'percent': "%2.1f%%"
                % (corrects_ratio * 100.0),
                'sensitivity': "%2.1f%%"
                % (sensitivity * 100.0),
                'specificity': "%2.1f%%"
                % (specificity * 100.0),
                'accuracy': "%2.1f%%"
                % (accuracy * 100.0),
                'group_size': group_total_submissions,
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
        #print method
        # Call the method as we return it
        return method(domain, uuid)

    def GET_stream(self, domain, uuid):
        block = False
        web.header("Content-Type", "text/event-stream")
        web.header('Cache-Control', 'no-cache')
        #web.header('Content-length:', 1000)
        while True:
            new_input.acquire()
            try:
                if block:
                    new_input.wait(timeout=30)
            finally:
                new_input.release()
            block = True

            data = self.compute_results(domain, uuid)
            data['dummy'] = config.dummy_data
            r = self.response(dumps(data))
            #print r
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


        return dumps(data, default=json_util.default)
