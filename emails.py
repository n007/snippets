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
DIGEST_SUBJECT = CONFIG.get('Emails','digest_subject')
EMAIL_SENDER = CONFIG.get('Emails','email_sender')
REMINDER_BODY = "Hey " + COMPANY_NAME + " Nerd,\n\n" + \
"Folks want to know what you're up to. Don't leave 'em hanging. Please send a bulleted list of your work items on their way."


class ReminderEmail(webapp.RequestHandler):
    def get(self):
        all_users = User.all().filter("enabled =", True).fetch(NUM_USERS)
        for user in all_users:
            #skip if weekly user and its not time for reminder, else set snippet date
            wkly = user.weekly;
            logging.debug("ReminderEmail weekly = %s ", wkly)
            if (time_for_reminder(wkly)):
                date = date_for_snippet(wkly)
            else:
                continue
            #check if snippet already exists for this date, if so don't remind
            try:
                snippet = Snippet.all().filter("date =", date).filter("user =", user).fetch(1)[0].text
                logging.debug("ReminderEmail snippets = %s ", snippet)
            except IndexError:
                logging.debug("ReminderEmail sending reminder to = %s ", user.email)
                subject = '[REMINDER] snippet time for '
                subject += 'week of ' if wkly else ''
                subject += date
                taskqueue.add(url='/onereminder', params={'email': user.email, 'sub': subject})


class OneReminderEmail(webapp.RequestHandler):
    def post(self):
        mail.send_mail(sender=EMAIL_SENDER,
                       to=self.request.get('email'),
                       subject=self.request.get('sub'),
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
        retval = snippet.title() 
        retval += '\n%s\n%s' % (divider, snippet.text)
        logging.debug("OneDigestEmail __snippet_to_text snippets = %s ", retval)
        return retval
        

    def get(self):
        post(self)


    def post(self):
        user = user_from_email(self.request.get('email'))
        all_users = User.all().fetch(NUM_USERS)
        following = compute_following(user, all_users)
        #Deal with weekly and daily snippets
        for wkly in (True, False):
            if (time_for_digest(wkly)):
                date = date_for_retrieval(wkly)
            else:
                continue    
            logging.debug("OneDigestEmail wkly = %s user = %s date = %s", wkly, user, date)
            all_snippets = Snippet.all().filter("date =", date).fetch(NUM_USERS)
            for s in all_snippets:
                e = s.user.email
                w = s.user.weekly
                logging.debug("OneDigestEmail s.user.email=%s s.user.weekly=%s", e, w)
                if (e in following and w == wkly):
                    body += '\n\n' + self.__snippet_to_text(s)
        if body:
            self.__send_mail(user.email, PROJECT_URL + '\n\n' + body)
        else:
            logging.info(user.email + ' not following anybody.')
