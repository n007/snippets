import logging

from google.appengine.api import mail
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from dateutil import *
from model import *

NUM_USERS=1000
REMINDER = """
Hey Rokcet Fuel Nerd,

Folks want to know what you're up to. Don't leave 'em hanging. Please send a bulleted list of your work item from this week on their way.
(Please remove your signature and any original text in the reply. Just keep the bulleted list.)

Read more about this porject at Rocket Fuel: 
https://docs.google.com/a/rocketfuelinc.com/document/d/1npaScAPm-Y8-w1x5ZpVmpsC-n-XchPZSk95ShOkgKaQ
"""



class ReminderEmail(webapp.RequestHandler):
    def get(self):
        all_users = User.all().filter("enabled =", True).fetch(NUM_USERS)
        for user in all_users:
            # TODO: Check if one has already been submitted for this period. If yes, skip.
            # TODO: Run accosicated cron from Friday evening to Monday morning
            taskqueue.add(url='/onereminder', params={'email': user.email})


class OneReminderEmail(webapp.RequestHandler):
    def post(self):
        mail.send_mail(sender="snippets <snippets@noted-tesla-574.appspotmail.com>",
                       to=self.request.get('email'),
                       subject="Snippet time!",
                       body=REMINDER)

    def get(self):
        post(self)

class DigestEmail(webapp.RequestHandler):
    def get(self):
        all_users = User.all().filter("enabled =", True).fetch(NUM_USERS)
        for user in all_users:
            taskqueue.add(url='/onedigest', params={'email': user.email})
            

class OneDigestEmail(webapp.RequestHandler):
    def __send_mail(self, recipient, body):
        mail.send_mail(sender="snippets <snippets@noted-tesla-574.appspotmail.com>",
                       to=recipient,
                       subject="Snippet delivery!",
                       body=body)

    def __snippet_to_text(self, snippet):
        divider = '-' * 30
        return '%s\n%s\n%s' % (snippet.user.pretty_name(), divider, snippet.text)

    def get(self):
        post(self)

    def post(self):
        user = user_from_email(self.request.get('email'))
        # This can be daily or weekly retrieval
        d = date_for_daily_retrieval()
        all_snippets = Snippet.all().filter("date =", d).fetch(500)
        all_users = User.all().fetch(NUM_USERS)
        following = compute_following(user, all_users)
        logging.info(all_snippets)
        body = '\n\n\n'.join([self.__snippet_to_text(s) for s in all_snippets if s.user.email in following])
        if body:
            self.__send_mail(user.email, 'https://noted-tesla-574.appspot.com\n\n' + body)
        else:
            logging.info(user.email + ' not following anybody.')
