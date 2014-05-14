import logging
import ConfigParser

from google.appengine.api import mail
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from dateutil import *
from model import *


CONFIG = ConfigParser.RawConfigParser()
CONFIG.read('configs/snippet.cfg')
NUM_USERS = CONFIG.getint('Global','num_users')
COMPANY_NAME = CONFIG.get('Global','company_name')
PROJECT_URL = CONFIG.get('Global','project_url')
REMINDER_SUBJECT = CONFIG.get('Emails','reminder_subject')
DIGEST_SUBJECT = CONFIG.get('Emails','digest_subject')
EMAIL_SENDER = CONFIG.get('Emails','email_sender')
REMINDER_BODY = "Hey " + COMPANY_NAME + " Nerd,\n\n" + \
"Folks want to know what you're up to. Don't leave 'em hanging. Please send a bulleted list of your work items on their way."


class ReminderEmail(webapp.RequestHandler):
    def get(self):
        date = date_for_snippet()
        all_users = User.all().filter("enabled =", True).fetch(NUM_USERS)
        for user in all_users:
            #If no snippet for this user this date, send a reminder
            try:
                snippet = Snippet.all().filter("date =", date).filter("user =", user).fetch(1)[0].text
                logging.debug("ReminderEmail snippets = %s ", snippet)
            except IndexError:
                logging.debug("ReminderEmail sending reminder to = %s ", user.email)
                taskqueue.add(url='/onereminder', params={'email': user.email})


class OneReminderEmail(webapp.RequestHandler):
    def post(self):
        mail.send_mail(sender=EMAIL_SENDER,
                       to=self.request.get('email'),
                       subject=REMINDER_SUBJECT,
                       body=REMINDER_BODY)

    def get(self):
        post(self)


class DigestEmail(webapp.RequestHandler):
    def get(self):
        all_users = User.all().filter("enabled =", True).fetch(NUM_USERS)
        for user in all_users:
            taskqueue.add(url='/onedigest', params={'email': user.email})
            

class OneDigestEmail(webapp.RequestHandler):
    def __send_mail(self, recipient, body):
        mail.send_mail(sender=EMAIL_SENDER,
                       to=recipient,
                       subject=DIGEST_SUBJECT,
                       body=body)

    def __snippet_to_text(self, snippet):
        divider = '-' * 30
        snippet = '%s\n%s\n%s' % (snippet.user.pretty_name(), divider, snippet.text)
        logging.debug("OneDigestEmail __snippet_to_text snippets = %s ", snippet)
        return snippet
        

    def get(self):
        post(self)

    def post(self):
        user = user_from_email(self.request.get('email'))
        date = date_for_retrieval()
        logging.debug("OneDigestEmail post user = %s date = %s ", user, date)
        all_snippets = Snippet.all().filter("date =", date).fetch(NUM_USERS)
        all_users = User.all().fetch(NUM_USERS)
        following = compute_following(user, all_users)
        body = '\n\n'.join([self.__snippet_to_text(s) for s in all_snippets if s.user.email in following])
        if body:
            self.__send_mail(user.email, PROJECT_URL + '\n\n' + body)
        else:
            logging.info(user.email + ' not following anybody.')
