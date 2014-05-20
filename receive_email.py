import datetime
import email
import logging
import re
import ConfigParser

from google.appengine.ext import webapp
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.ext.webapp import util

from dateutil import *
from model import *

CONFIG = ConfigParser.RawConfigParser()
CONFIG.read('configs/snippet.cfg')
NUM_USERS = CONFIG.getint('Global','num_users')


class ReceiveEmail(InboundMailHandler):
    #Receive a snippet email and create or replace snippetS

    def receive(self, message):
        user = user_from_email(email.utils.parseaddr(message.sender)[1])
        signature = email.utils.parseaddr(message.sender)[0]
        subject = message.subject
        date = date_for_snippet(user.weekly)
        logging.debug("ReminderEmail sender = %s, signature = %s ", message.sender, signature)
        logging.debug("ReminderEmail subject = %s, date = %s", subject, date)
        match=re.search(r'(\d+-\d+-\d+)', subject)
        try:
            date_override = match.group(1)
            logging.debug("ReminderEmail found date pattern in subject = %s", date_override)
            date = datetime.datetime.strptime(date_override, '%Y-%m-%d').date()
        except AttributeError:
            logging.info("ReminderEmail, normal snippet, no override or backfill is needed")

        for content_type, body in message.bodies('text/plain'):
            if body.encoding == '8bit':
                body.encoding = '7bit'
            content = body.decode()
            #logging.debug("ReminderEmail content = %s ", content)

            sig_pattern = re.compile(r'^\-\-\s*$', re.MULTILINE)
            split_email = re.split(sig_pattern, content)
            content = split_email[0]
            #logging.debug("ReminderEmail content = %s ", content)
            
            reply_pattern = re.compile(r'^On.*at.*snippets', re.MULTILINE)
            split_email = re.split(reply_pattern, content)
            content = split_email[0]
            #logging.debug("ReminderEmail content = %s ", content)
            
            reply_pattern = re.compile(r'.*' + signature + '.*', re.MULTILINE)
            split_email = re.split(reply_pattern, content)
            content = split_email[0]
            #logging.debug("ReminderEmail content = %s ", content)
            
            create_or_replace_snippet(user, content, date)


def main():
    application = webapp.WSGIApplication([ReceiveEmail.mapping()], debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()


