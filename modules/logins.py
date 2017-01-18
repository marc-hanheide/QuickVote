from modules.common import *
from modules.domains import qv_domains

# new login collection
qv_logins = qv_db['logins']
qv_logins.create_index([('Username',ASCENDING)],unique=True)

# create default login if no login exists
if qv_logins.find().count() == 0:
    qv_logins.insert({
        'Username' : 'Admin',
        'Password' : hmac.new(b'QVkey123', '1234'.encode('utf-8'), hashlib.sha512).hexdigest(), # hash methods in python 3 require the key (and message) to be a byte array. See https://docs.python.org/3/library/hmac.html
        'isAdmin'  : True
    })

# new login session
qv_sessions = qv_db['sessions']
qv_sessions.create_index([('createdAt',DESCENDING)],expireAfterSeconds=24*60*60)
qv_sessions.create_index([('Username',DESCENDING)],unique=True)
### END

class loginmanager:

	# creates random string of letters and digits for extra unique hashing
	def RandomString(self,N):
		r = ""
		for i in range(0, N):
			r += random.choice(string.ascii_lowercase + string.digits)
		return r

	# create session in qv_sessions and create cookies
	def Login(self,user):
		global qv_sessions
		sesunhash_tmp = user + str(datetime.utcnow()) + self.RandomString(10)
		seshash_tmp = hmac.new( b'QVkey123', sesunhash_tmp.encode('utf-8'), hashlib.sha512).hexdigest()
		if qv_sessions.find_one({"Username" : user}) != None:
			qv_sessions.delete_one({"Username" : user})
		try:
			# create session in qv_sessions
			qv_sessions.insert({'createdAt' : datetime.utcnow(), 'Username' : user, 'QV_Ses' : seshash_tmp})
		except:
			print ("Session Creation Failed!")
			return False
		# create session cookies
		web.setcookie('QV_Usr',user)
		web.setcookie('QV_Ses',seshash_tmp)
		return True

	# Check if user is logged into system
	def LoggedIn(self):
		# Retrieve information stored in cookies
		usr = web.cookies().get('QV_Usr')
		ses = web.cookies().get('QV_Ses')

		# test if cookies existed
		if usr != None and ses != None:
			# retrieve session info for usr
			rec = qv_sessions.find_one({'Username' : usr})

			# test if session information matches
			if rec != None:
				if rec['QV_Ses'].encode("utf-8") == ses:
					print ("Logged In")
					return True
		return False

	# Logout user
	def Logout(self):
		# Retrieve information stored in cookies
		usr = web.cookies().get('QV_Usr')
		ses = web.cookies().get('QV_Ses')

		# test if cookies existed
		if usr != None and ses != None:
			# retrieve session info for usr
			rec = qv_sessions.find_one({'Username' : usr})

			# test if session information matches
			if rec != None:
				if rec['QV_Ses'].encode("utf-8") == ses:
					# Remove session from mongodb
					qv_sessions.delete_one({'Username' : usr})

					# overwrite cookie data as blank
					web.setcookie('QV_Usr','')
					web.setcookie('QV_Ses','')

					print ("Logged Out")
					return True
		print ("Logout failed!")
		return False

	def DomainLogin(self,domain):
		# check logged in
		if not logman.LoggedIn():
			print ("Failed Login!")
			return False

		# check for valid domain
		if not qv_domains.is_domain(domain):
			print ("Failed domain check!")
			return False

		# check that user has access to this domain
		attempt_at_access = qv_domains.Access_domain(domain,web.cookies().get('QV_Usr'))
		if  logman.isAdmin() or attempt_at_access == "Coord" or attempt_at_access == "Editor":
			print ("Authourized")
			return True
		else:
			print ("Failed Access!")
			return False

	def isAdmin(self):
		if self.LoggedIn():
			return qv_logins.find_one({'Username' : web.cookies().get('QV_Usr')})['isAdmin']
		return False
logman = loginmanager()

class UserManager:
	def get_usr_list(self):
		if logman.isAdmin():
			recs = qv_logins.find({"Username" : {"$exists" : True}})
			if recs != None:
				return recs
		return None

	def make_user_admin(self,usr):
		if logman.isAdmin():
			r = qv_logins.find_one({"Username" : usr})
			if r != None:
				r["isAdmin"] = True
				qv_logins.save(r)
				return True
		return False
	def change_user_password(self,usr,passw):
		if logman.isAdmin():
			r = qv_logins.find_one({"Username" : usr})
			if r != None:
				r["Password"] = hmac.new('QVkey123',passw,hashlib.sha512).hexdigest()
				qv_logins.save(r)
				return True
		return False
	def revoke_user_admin(self,usr):
		if logman.isAdmin():
			r = qv_logins.find_one({"Username" : usr})
			if r != None:
				r["isAdmin"] = False
				qv_logins.save(r)
				return True
		return False
	def delete_user(self,usr):
		if logman.isAdmin():
			try:
				qv_logins.delete_one({"Username" : usr})
				return True
			except:
				return False
		return False
	def create_user(self,usr,passw,admin):
		if logman.isAdmin():
			try:
				qv_logins.insert({
					'Username' : usr,
					'Password' : hmac.new('QVkey123',passw,hashlib.sha512).hexdigest(),
					'isAdmin'  : admin
				})
				return True
			except:
				return False

usrman = UserManager()
