import sys
import os
abspath = os.path.dirname(__file__)
print abspath

if len(abspath) > 0:
    sys.path.append(abspath)
    os.chdir(abspath)

# common imports
from modules.common import *
import modules.glob as glob

from web import form

import signal

from os import _exit
import time

from urlparse import urlparse

from modules.PageServer import *

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
    v['url_pattern'] = path_prefix + v['pattern'][1:].replace('(.+)', '%s')
    print '(%s, %s, %s)' % (v['pattern'], v['class'], v['url_pattern'])

def signal_handler(signum, frame):
    print "stopped."
    _exit(signal.SIGTERM)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run()
else:
    application = app.wsgifunc()
