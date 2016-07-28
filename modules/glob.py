from uuid import uuid4
session_uuid = uuid4()
admin_uuid = uuid4()

urls = {
	# display filterable list of domains
	'home':
	{'pattern'	: '/',
	 'class'	: 'home',
	 'method'	: 'get'
	 },
	# manage domain
	'manage':
	{'pattern' 	: '/(.+)/manage',
	 'class'	: 'manage',
	 'method'	: 'get'
	},
	# edit / remove / add new domains
	'EditDom':
	{'pattern' 	: '/(.+)/EditDom/(.+)',
	 'class'	: 'EditDom',
	 'method'	: 'post'
	},
	'MainageDomainUsers':
	{'pattern' 	: '/(.+)/manage/update',
	 'class'	: 'MainageDomainUsers',
	 'method'	: 'post'
	},
	# login page
	 'mainlogin':
	{'pattern'	: '/login',
	 'class'	: 'mainlogin',
	 'method'	: 'get'
	 },
	 'users':
 	{'pattern'	: '/users',
 	 'class'	: 'Users',
 	 'method'	: 'get'
 	 },
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
