import datetime
import functools
import logging
import os
import urllib
import ConfigParser

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from emails import *
from model import *


CONFIG = ConfigParser.RawConfigParser()
CONFIG.read('configs/snippet.cfg')
COMPANY_NAME = CONFIG.get('Global','company_name')
NUM_USERS = CONFIG.getint('Global','num_users')
ADMIN_USERS = CONFIG.get('Global','admin').split()
DEFAULT_TAGLIST_COUNT = 3

# Constants for generating usage statistics.
MAX_SNIPPET_DELAY_DAYS = 3
REGULAR_WEEKLY_WINDOW = 8
REGULAR_DAILY_WINDOW = 20


def is_rocketfuel_user(email_id):
    """Checks if the given email_id belongs to desired domain(s)."""
    if not email_id:
        return False
    email_domain = email_id.split('@')[1]
    return any([email_domain.endswith(domain) for domain in EMAIL_DOMAINS])


def is_admin_user(email_id):
    """Checks if the given email_id belongs to set of app admin."""
    if not email_id:
        return False
    user_id = email_id.split('@')[0]
    return user_id in ADMIN_USERS


def authenticated(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        # TODO: handle post requests separately
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri),
                          permanent=True)
            return None
        elif not is_rocketfuel_user(user.email()):
            self.redirect('/login', permanent=True)
            return None
        return method(self, *args, **kwargs)
    return wrapper


def requires_admin(method):
    """Function decorator for forcing admin privileges."""
    @authenticated
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        user = users.get_current_user()
        if not is_admin_user(user.email()):
            self.redirect('/', permanent=True)
        return method(self, *args, **kwargs)
    return wrapper


class BaseHandler(webapp.RequestHandler):
    """Base handler class. All other classes should inherit this."""

    user_db_obj = None

    @authenticated
    def get_or_add_user(self):
        """We cannot afford to check/add user as it creates duplicate entries
        due to late data write to datastore."""
        user = users.get_current_user()
        userObj = User.all().filter("email =", user.email()).fetch(1)
        if not userObj:
            userObj = User(email=user.email())
            userObj.put()
        else:
            userObj = userObj[0]
        return userObj

    @authenticated
    def get_user(self):
        """Return current user DB object. Authenticated wrapper ensures that
        the user is logged in using an allowed domain."""
        if not self.user_db_obj:
            self.user_db_obj = self.get_or_add_user()
        return self.user_db_obj

    def _get_user_details(self):
        """Returns details for current user."""
        user = users.get_current_user()
        data = {'email_id': user.email(), 'company_name': COMPANY_NAME,
                'logout_url': users.create_logout_url(self.request.uri),
                'login_url': users.create_login_url(), 'user': None,
                'company_name': COMPANY_NAME}
        if not user or not is_rocketfuel_user(user.email()):
            return data

        user = self.get_user()
        data['full_name'] = user.pretty_name()
        data['user'] = user
        data['admin_user'] = is_admin_user(user.email)
        return data


    def render(self, template_name, template_values):
        #self.response.headers['Content-Type'] = 'text/html'
        path = os.path.join(os.path.dirname(__file__), 'templates/%s.html' % template_name)
        if not template_values:
            template_values = dict()
        template_values['current_user_details'] = self._get_user_details()

        self.response.out.write(template.render(path, template_values))


class ErrorHandler(BaseHandler):
    """Handle all errors."""

    def get(self, error_type):
        """Given an error_type render the error page."""
        self.render('error', dict(error_type=error_type))


class UserLogin(BaseHandler):
    """Handles user login issues."""

    def get(self):
        """Handler for GET request. Force to login using company email id."""
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(), permanent=True)
        elif is_rocketfuel_user(user.email()):
            self.redirect('/', permanent=True)
        else:
            return self.redirect('/error/invalid_domain', permanent=True)


class UserHandler(BaseHandler):
    #Show a given user's snippets.

    @authenticated
    def post(self, email):
        """Handler for post request."""
        user = users.get_current_user()
        if user.email() != email:
            self.redirect('/', permanent=True)
        user = self.get_user()
        user.display_name = self.request.get('user_name')
        user.enabled = True if self.request.get('enable_reminder') == "on" else False
        user.weekly = True if self.request.get('frequency') == "weekly" else False
        user.tags = [self.request.get('group')]
        user.put()
        self.redirect('/', permanent=True)

    @authenticated
    def get(self, email):
        user = self.get_user()
        count = int(self.request.get('count') or DEFAULT_TAGLIST_COUNT)
        email = urllib.unquote_plus(email)
        desired_user = user_from_email(email)
        snippets = desired_user.snippet_set
        snippets = sorted(snippets, key=lambda s: s.date, reverse=True)[0:count]
        following = email in user.following or any(set(desired_user.tags).intersection(user.tags))
        tags = [(t, t in user.tags_following or t in user.tags) for t in desired_user.tags]
        template_values = {
                           'current_user' : user,
                           'user': desired_user,
                           'snippets': snippets,
                           'following': following,
                           'count_to_show': count,
                           'tags': tags
                           }
        self.render('user', template_values)


class FollowHandler(BaseHandler):
    #Follow a user or tag.
    @authenticated
    def get(self):
        user = self.get_user()
        desired_tag = self.request.get('tag')
        desired_user = self.request.get('user')
        continue_url = self.request.get('continue')
        if desired_tag and (desired_tag not in user.tags_following):
            user.tags_following.append(desired_tag)
            user.put()
        if desired_user and (desired_user not in user.following):
            user.following.append(desired_user)
            user.put()

        self.redirect(continue_url, permanent=True)


class UnfollowHandler(BaseHandler):
    #Unfollow a user or tag.
    @authenticated
    def get(self):
        user = self.get_user()
        desired_tag = self.request.get('tag')
        desired_user = self.request.get('user')
        continue_url = self.request.get('continue')
        if desired_tag and (desired_tag in user.tags_following):
            user.tags_following.remove(desired_tag)
            user.put()
        if desired_user and (desired_user in user.following):
            user.following.remove(desired_user)
            user.put()

        self.redirect(continue_url, permanent=True)


class TagHandler(BaseHandler):
    #View this week's snippets in a given tag.
    @authenticated
    def get(self, tag):
        """Handler for get request."""
        def filter_by_date(snippets, start_date, end_date):
            """Filters given list of snippets by count."""
            filtered = [snippet for snippet in snippets
                                    if snippet.date <= end_date and
                                       snippet.date >= start_date]
            return filtered

        count = self.request.get('count') or DEFAULT_TAGLIST_COUNT
        count = int(count)
        start_date = html5_parse_date(self.request.get('sd'))
        end_date = html5_parse_date(self.request.get('ed'))
        user = self.get_user()
        following = tag in user.tags_following or tag in user.tags
        all_snippets = []

        all_users = User.all()
        users_in_tag = [user for user in all_users if tag in user.tags]
        for user in users_in_tag:
            data = {'name': user.pretty_name()}
            snippets = sorted(user.snippet_set, key=lambda x:x.date,
                              reverse=True)
            if start_date and end_date:
                snippets = filter_by_date(snippets, start_date, end_date)
            else:
                snippets = snippets[0:count]
            data['snippets'] = snippets
            all_snippets.append(data)

        all_snippets = sorted(all_snippets, key=lambda x:x['name'])
        start_date = start_date or get_past_date(7)
        end_date = end_date or get_today_date()
        template_values = {
                           'current_user' : user,
                           'all_snippets': all_snippets,
                           'following': following,
                           'tag': tag,
                           'count_to_show': count,
                           'start_date': html5_date(start_date),
                           'end_date': html5_date(end_date)
                           }
        self.render('tag', template_values)


class MainHandler(BaseHandler):
    #Show list of all users and acting user's settings.

    @authenticated
    def get(self):
        user = self.get_user()
        # Fetch user list and display
        # User tags set is somewhat redundant. A user better be part of one
        # group only. For now if a user belongs to multiple groups, his/her
        # name will appear in list of all users of those groups.
        tag_groups = []
        raw_users = User.all().order('email').fetch(NUM_USERS)
        following = compute_following(user, raw_users)
        all_tags = set()
        for u in raw_users:
            all_tags.update(u.tags)
        for tag in all_tags:
            tag_info = {'name': tag, 'following': tag in user.tags_following or
                                                  tag in user.tags }
            tag_users = [(u, u.email in following) for u in raw_users
                                                   if tag in u.tags]
            tag_info['users'] = sorted(tag_users,
                                       key=lambda x:x[0].pretty_name())
            following_count = sum(x[1] for x in tag_users)
            tag_info['users_following_count'] = following_count
            tag_groups.append(tag_info)
        tag_groups = sorted(tag_groups, key=lambda x:x['name'])
        template_values = {'current_user': user, 'all_users': tag_groups,
                           'tag_groups': tag_groups}
        self.render('index', template_values)


class FAQHandler(BaseHandler):
    #View this week's snippets in a given tag.
    @authenticated
    def get(self):
        self.render('faq', {})


class GenerateUserReport(BaseHandler):
    """It prepares list of active, inactive users."""

    @authenticated
    def get(self):
        """Generate lists and update db."""
        starting_date_weekly_users = get_past_date(REGULAR_WEEKLY_WINDOW * 7)
        starting_date_daily_users = get_past_date(REGULAR_DAILY_WINDOW)

        snippets = Snippet.all().filter("date >=", starting_date_weekly_users).order("-date")
        snippets = snippets.fetch(snippets.count())
        users = User.all()
        regular_daily, regular_weekly, snippet_pending = [], [], []
        prev_week = date_for_weekly_snippet()
        today = get_today_date()
        for user in users:
            user_snippets = sorted([s for s in snippets if s.user.email == user.email],
                                   key=lambda x:x.date, reverse=True)
            if user.weekly:
                if len(user_snippets) >= REGULAR_WEEKLY_WINDOW - 1:
                    regular_weekly.append(user)
                if (not user_snippets or (prev_week != user_snippets[0].date and
                    today > prev_week + delta_days(MAX_SNIPPET_DELAY_DAYS))):
                    snippet_pending.append(user)
            elif not user.weekly:
                user_snippets = [s for s in user_snippets
                                 if s.date >= starting_date_daily_users]
                if len(user_snippets) >= REGULAR_DAILY_WINDOW - 7:
                    regular_daily.append(user)
                if (not user_snippets == 0 or
                    today > user_snippets[0].date + delta_days(MAX_SNIPPET_DELAY_DAYS)):
                    snippet_pending.append(user)
        template_values = {
                'regular_daily': sorted(regular_daily, key=lambda x:x.pretty_name()),
                'regular_weekly': sorted(regular_weekly, key=lambda x:x.pretty_name()),
                'snippet_pending': sorted(snippet_pending, key=lambda x:x.pretty_name())}
        self.render('user_activity', template_values)


class EmailAllUsers(BaseHandler):
    """Handler for emailing all the users."""

    @requires_admin
    def post(self):
        """Send email to all the users."""
        message = self.request.get('message')
        subject = self.request.get('subject')
        all_users = User.all()
        user_list = []
        for user in all_users:
            send_email(user.email, subject, message)
            user_list.append(user.user_id())
        self.render('send_email', {'sent_to': user_list})

    @requires_admin
    def get(self):
        """Render send email form."""
        self.render('send_email', {})


def main():
    application = webapp.WSGIApplication(
                                         [('/', MainHandler),
                                          ('/login', UserLogin),
                                          ('/user/(.*)', UserHandler),
                                          ('/tag/(.*)', TagHandler),
                                          ('/error/(.*)', ErrorHandler),
                                          ('/follow', FollowHandler),
                                          ('/unfollow', UnfollowHandler),
                                          ('/reminderemail', ReminderEmail),
                                          ('/digestemail', DigestEmail),
                                          ('/onereminder', OneReminderEmail),
                                          ('/onedigest', OneDigestEmail),
                                          ('/user_activity', GenerateUserReport),
                                          ('/email_all', EmailAllUsers),
                                          ('/faq', FAQHandler)],
                                          debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
