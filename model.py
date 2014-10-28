import logging
import re
import ConfigParser

from google.appengine.api import users
from google.appengine.ext import db

CONFIG = ConfigParser.RawConfigParser()
CONFIG.read('configs/snippet.cfg')
EMAIL_REPALCE_FROM = CONFIG.get('Model','email_replace_from')
EMAIL_REPALCE_TO = CONFIG.get('Model','email_replace_to')
EMAIL_DOMAINS = CONFIG.get('Model', 'email_domains').split()
SIG_PATTERN = CONFIG.get('Emails','signature_pattern')
DEFAULT_USER_TAGS = ['engineering']

class User(db.Model):
    email = db.StringProperty()
    display_name = db.StringProperty(default='')
    following = db.StringListProperty()
    enabled = db.BooleanProperty(default=True)
    tags = db.StringListProperty(default=DEFAULT_USER_TAGS)
    tags_following = db.StringListProperty()
    weekly = db.BooleanProperty(default=True)

    def user_id(self):
        return self.email.split('@')[0]

    def pretty_name(self):
        return self.display_name or self.user_id()

    def first_name(self):
        if self.display_name:
            return self.display_name.split()[0]
        else:
            return self.user_id()

    def last_name(self):
        if self.display_name:
            return self.display_name.split()[-1]
        else:
            return None

class Snippet(db.Model):
    user = db.ReferenceProperty(User)
    text = db.TextProperty()
    date = db.DateProperty()
    weekly = db.BooleanProperty(default=True)

    def title(self):
      return self.user_title() + ' ' + self.date_title()

    def user_title(self):
      return self.user.pretty_name() + '\'s snippet'

    def date_title(self):
      if(self.weekly):
        return 'for week of ' + str(self.date)
      else:
        return 'for ' + str(self.date)

    def trimmed_text(self):
        return extract_snippets_from_msg(self.text.strip(), self.user)


def compute_following(current_user, users):
    #Return set of email addresses being followed by this user.
    following = set()
    email_set = set(current_user.following)
    tag_set = set(current_user.tags_following)
    #Always self and self group follower
    email_set.add(current_user.email)
    try:
        tag_set.add(current_user.tags[-1])
    except IndexError:
        logging.warning("computing groups following without group for user=%s", current_user.email)
    #logging.debug("compute_following, user = %s ", current_user.email)
    for u in users:
        if ((u.email in email_set) or
            (len(tag_set.intersection(u.tags)) > 0)):
            following.add(u.email)
            #logging.debug("compute_following, user = %s ", u.email)
    return following


def user_from_email(email):
    #Handle emails from rocketfuel.com domain as if rocketfuelinc.com
    email = email.replace(EMAIL_REPALCE_FROM, EMAIL_REPALCE_TO, 1);
    #logging.debug("user_from_email email = %s ", email)
    return User.all().filter("email =", email).fetch(1)[0]


def create_or_replace_snippet(user, text, date, weekly):
    if (text == ''):
        logging.warning("create_or_replace_snippet, got empty snippet: %s, %s ", user, date)
        return
    #Delete existing snippets(yeah, yeah, should be a transaction)
    #Handling by fetching few (instead 1) and deleting them
    #TODO: add transaction support
    TRANS_SALT=10
    for existing in Snippet.all().filter("date =", date).filter("user =", user).fetch(TRANS_SALT):
        existing.delete()
    # Write new
    snippet = Snippet(text=text, user=user, date=date, weekly=weekly)
    snippet.put()
    #logging.debug("create_or_replace_snippet user=%s, date=%s, weekly=%s, text=%s  ", user, date, weekly, text)


def extract_snippets_from_msg(content, user):
    """Given plain text body of a message, it tries to remove unwanted content
    from message like signature, content from previous emails etc."""
    # Note: Remember unwanted information is better than loosing information!!
    user_sig = '{}{}'.format(user.user_id(), SIG_PATTERN)
    #content = content.replace('<br>', '')

    # Strip signatures beginning with --
    pattern = re.compile(r'^\-\-\s*$', re.MULTILINE)
    content = re.split(pattern, content)[0]

    # Should match "On Sat, Oct 4, 2014 at 6:15 AM, (snippets|userid@domain)
    pattern = (r'On.*[0-9]{4}.*(AM|PM).*(snippets|' + user_sig + ').*')
    re_pattern = re.compile(pattern, re.MULTILINE)
    content = re.split(re_pattern, content)[0]

    # Strip signatures matching *<NAME> .. *
    re_pattern = re.compile(r'^\*.*' + user_sig + '.*', re.MULTILINE)
    content = re.split(re_pattern, content)[0]

    # Strip signatures matching ~Name
    pattern = r'^~({}|{}|{})\s*$'.format(user.user_id(), user.pretty_name(),
                                      user.first_name())
    re_pattern = re.compile(pattern, re.MULTILINE)
    content = re.split(re_pattern, content)[0]

    pattern = r'^(thanks|thx),?\s*$'
    re_pattern = re.compile(pattern, re.MULTILINE|re.IGNORECASE)
    content = re.split(re_pattern, content)[0]
    return content.strip()
