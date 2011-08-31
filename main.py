#!/usr/bin/env python

import logging, datetime, time, urllib

import wsgiref.handlers
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users, urlfetch
from google.appengine.api.labs import taskqueue

logging.getLogger().setLevel(logging.DEBUG)

#def baseN(num,b,numerals="0123456789abcdefghijklmnopqrstuvwxyz"): 
def baseN(num,b,numerals="abcdefghijklmnopqrstuvwxyz"): 
    return ((num == 0) and  "0" ) or (baseN(num // b, b).lstrip("0") + numerals[num % b])


class KronHook(db.Model):
    user     = db.UserProperty(auto_current_user_add=True)
    interval = db.IntegerProperty(required=True)
    name     = db.StringProperty(required=True)
    rid      = db.StringProperty(required=True)
    created  = db.DateTimeProperty(auto_now_add=True)
    updated  = db.DateTimeProperty(auto_now=True)
    
    def __init__(self, *args, **kwargs):
        kwargs['name'] = kwargs.get('name', baseN(abs(hash(time.time())), 26))
        super(KronHook, self).__init__(*args, **kwargs)
    
    def __str__(self):
        return self.name


class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        admin = users.is_current_user_admin()
        if user:
            logout_url = users.create_logout_url("/")
            hooks = KronHook.all().filter('user =', user)
        else:
            login_url = users.create_login_url('/')
        self.response.out.write(template.render('templates/main.html', locals()))
    
    def post(self):
        if self.request.POST.get('name', None):
            h = KronHook.all().filter('name =', self.request.POST['name']).get()
            h.delete()
        else:
            admin = users.is_current_user_admin()
            interval=int(self.request.POST['interval'])
            # only admins can have 1 min cronjobs
            if not admin and interval == 1:
                self.redirect('/')
            h = KronHook(interval=interval, rid=self.request.POST['rid'])
            h.put()
        self.redirect('/')


class CronHandler(webapp.RequestHandler):
    def get(self, interval):
        ii = int(interval)
        if ii not in [1, 5, 10, 30, 60]:
            self.error(400)
            return self.response.out.write('400 Invalid Request')
        for h in KronHook.all().filter('interval =', ii):
            # hook_url = "http://webhooks.kynetxapps.net/h/" + h.rid + "/kronhook"
            hook_url = "http://cs.kobj.net/blue/event/kronhook/" + h.name + "/" + h.rid
            taskqueue.add(url="/post/" + h.name, params={"url": hook_url, "interval": str(interval)})
            # logging.debug('Event URL: %s', hook_url)
        return self.response.out.write("OK")


class PostHandler(webapp.RequestHandler):
    def post(self, name):
        try:
            now = datetime.datetime.now()
            params = {"hook.name": name,
                      "hook.interval": self.request.POST['interval'],
                      "hook.time": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
            urlfetch.fetch(url=self.request.POST['url'], 
                           payload=urllib.urlencode(params), 
                           method='POST',
                           deadline=30)
        except Exception, e:
            logging.error('problem: %s' % repr(e))
            pass


def main():
  application = webapp.WSGIApplication([
    ('/cron/(1|5|10|30|60)$', CronHandler),
    ('/post/([a-z0-9]+)',   PostHandler),
    ('/', MainHandler)], debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
