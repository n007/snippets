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
SIG_PATTERN = CONFIG.get('Emails','signature_pattern')

class ReceiveEmail(InboundMailHandler):
    #Receive a snippet email and create or replace snippetS

    def receive(self, message):
        user = user_from_email(email.utils.parseaddr(message.sender)[1])
        signature = user.pretty_name() + SIG_PATTERN
        subject = message.subject
        wkly = user.weekly
        date = date_for_snippet(wkly)
        logging.debug("ReminderEmail sender = %s, signature = %s ", message.sender, signature)
        logging.debug("ReminderEmail subject = %s, date = %s", subject, date)
        match=re.search(r'(\d+-\d+-\d+)', subject)
        try:
            date_override = match.group(1)
            logging.debug("ReminderEmail found date pattern in subject = %s", date_override)
            new_date = datetime.datetime.strptime(date_override, '%Y-%m-%d').date()
            #check if its daily or weekly and do some sanity checks
            backfill = new_date < date
            if ('week of' in subject and isweeklysnippetday(new_date) and backfill):
                wkly = True
                date = new_date
            elif (backfill):
                wkly = False
                date = new_date
            else:
                logging.info("ReminderEmail, date override is skipped. Either normal snippet or invalid override dates.")      

        except AttributeError:
            logging.info("ReminderEmail, likely normal snippet with subject edited, handle with default dates")

        for content_type, body in message.bodies('text/plain'):
            if body.encoding == '8bit':
                body.encoding = '7bit'
            content = body.decode()
            #logging.debug("ReminderEmail content = %s ", content)

            sig_pattern = re.compile(r'^\-\-\s*$', re.MULTILINE)
            split_email = re.split(sig_pattern, content)
            content = split_email[0]
            #logging.debug("ReminderEmail content = %s ", content)
            
            reply_pattern = re.compile(r'On.*at.*snippets', re.MULTILINE)
            split_email = re.split(reply_pattern, content)
            content = split_email[0]
            #logging.debug("ReminderEmail content = %s ", content)
            
            reply_pattern = re.compile(r'.*' + signature + '.*', re.MULTILINE)
            split_email = re.split(reply_pattern, content)
            content = split_email[0]
            #logging.debug("ReminderEmail content = %s ", content)
            
            create_or_replace_snippet(user, content, date, wkly)


def main():
    application = webapp.WSGIApplication([ReceiveEmail.mapping()], debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()


