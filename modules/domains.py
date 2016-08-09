# common imports
from modules.common import *
import modules.glob as glob

import math

class domain_manager:

	def __init__(self, db):
		self.domain_coll = db['domains']
		self.ensure_debug_domain()
		self.domain_coll.create_index('name', unique=True)
		self.domain_coll.create_index('admin_url', unique=True)
		self.domain_coll.create_index([('lastActive',DESCENDING)],unique=False)

	def ensure_debug_domain(self):
		# ensure testdomain
		if self.domain_coll.find_one({'name': 'debug'}) is None:
			self.domain_coll.insert(
				{
					'name': 'debug',
					'inserted_at': datetime.now(),
                    'lastActive': datetime.now(),
					'lastEdited': datetime.now(),
					'lastEditedBy': "N/A",
					'admin_url': str(uuid4()),
					'active_question': None,
					'users' : []
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
		glob.session_uuid
		c = self.domain_coll.find_one({'name': domain})
		if c is None:
			raise RuntimeError('domain %s not in database' % domain)
		c['active_question'] = uuid
		self.domain_coll.save(c)
		glob.session_uuid = self.get_active_session(domain, uuid)

	def set_active_session(self, domain, quuid, suuid=None):
		glob.session_uuid
		c = self.domain_coll.find_one({'name': domain})
		if c is None:
			raise RuntimeError('domain %s not in database' % domain)
		if 'session' not in c:
			print "NOT IN YET"
			c['session'] = {}
		if suuid is None:
			suuid = str(uuid4())
		c['session'][quuid] = suuid
		glob.session_uuid = suuid
		self.domain_coll.save(c)
		return suuid



	def get_active_session(self, domain, quuid):
		c = self.domain_coll.find_one({'name': domain})
		if 'session' not in c:
			c['session'] = {}

		if quuid not in c['session']:
			return self.set_active_session(domain, quuid)

		return c['session'][quuid]


	# Check that domain exists
	def is_domain(self,domain):
		# ensure domain is safe (alphanumeric)
		if domain.isalnum() == False:
			if domain.isalpha() == False:
				if domain.isdigit() == False:
					return False

		# test if domain exists
		if self.domain_coll.find_one({'name' : domain}) == None:
			return False
		return True

	# Test if user has access to domain and what that access is
	def Access_domain(self,domain,user):
		# check domain exists
		if not self.is_domain(domain):
			return None
		# get user's access from domain
		print "finding - " + str('users.'+user)
		access = self.domain_coll.find_one({'name' : domain, 'users' : {"$exists" : True}})

		# return user's level of access or none
		if access == None:
			print "Access Denied!"
			return None

		usr_exists = False
		permission = ""
		try:
			for i in access['users']:
				print i
				if i[0] == user:
					usr_exists = True
					permission = i[1]
					break
		except:
			return None

		if usr_exists:
			print permission
			self.DomainActive(domain)   # Update last active time of domain
			return permission
		else:
			return None

			# Get names of all domains
	def get_list_of_domains(self):
		rec = self.domain_coll.find({'lastActive' : {'$exists' : True}})
		if rec == None:
			return None
		list = []
		for r in rec:
			tst = abs(datetime.now() - r['lastActive'])
			td = int(tst.days) # days
			th = int(math.floor(tst.total_seconds()/(60*60))) # hours
			tm = int(math.floor((tst.total_seconds()/60)%60)) # minutes
			print "{} days, {} hrs, {} mins".format(td,th,tm)
			q = ""
			if r['active_question'] == None:
				q = "N/A"
			else:
				q = qv_questions.find_one({'uuid' : r['active_question']})['question']
			list.append([r['name']," {} hrs {} mins".format(th,tm),q,""])
		return list

	# update last active time of domain
	def DomainActive(self,domain):
		if self.is_domain(domain):
			rec = self.domain_coll.update({'name' : domain},{'$set' : {'lastActive' : datetime.now()}})
			print "Domain Active - " + str(datetime.now())

	# retrieve a list of editors for coordinators to manage
	def get_list_of_editors(self,domain):
		if self.is_domain(domain):
			recs = self.domain_coll.find_one({"name" : domain})
			usr_list = []
			for l in recs['users']:
				if l[1] == 'Editor':
					usr_list.append(l[0])
			print usr_list
			if len(usr_list) == 0:
				return None
			return usr_list
		return None

	# retrieve a list of user for admins to manage
	def get_list_of_users(self,domain):
		if self.is_domain(domain):
			recs = self.domain_coll.find_one({"name" : domain})
			print "get_list_of_users: "
			print recs
			return recs['users']
		return None

	# update the list of editors from list sent through domain manager, return false if failed to update else true
	def update_list_of_editors(self,domain,editor_list):
		if self.is_domain(domain):
			recs = self.domain_coll.find_one({"name" : domain})
			updated_list = []
			for r in recs['users']:
				if r[1] == 'Coord' or r[1] == 'Admin':
					updated_list.append(r)

			for r in range(len(editor_list)):
				updated_list.append([editor_list[str(r)],"Editor"])
			print updated_list
			self.domain_coll.update({'name' : domain},{'$set' : {'users' : updated_list}})
			return True
		return False

	# update the list of all users from list sent through domain manager, return false if failed to update else true
	def update_list_of_all(self,domain,usr_list):
		if self.is_domain(domain):
			updated_list = []
			for r in range(len(usr_list)/2):
				updated_list.append([usr_list[str(r)],usr_list["drop" + str(r)]])
			self.domain_coll.update({'name' : domain},{'$set' : {'users' : updated_list}})
			return True
		return False

qv_domains = domain_manager(qv_db)
