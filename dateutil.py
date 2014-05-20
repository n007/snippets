import logging
import datetime
import ConfigParser

from datetime import tzinfo, timedelta


CONFIG = ConfigParser.RawConfigParser()
CONFIG.read('configs/snippet.cfg')
SNIPPET_PERIOD = CONFIG.get('DateTimeUtil','snippet_period')

class USTimeZone(tzinfo):

    def __init__(self, hours, reprname, stdname, dstname):
        self.stdoffset = timedelta(hours=hours)
        self.reprname = reprname
        self.stdname = stdname
        self.dstname = dstname

    def __repr__(self):
        return self.reprname
        
    def __firstsunday(self, dt):
        #First Sunday on or after dt.
        return dt + datetime.timedelta(days=(6-dt.weekday()))

    def utcoffset(self, dt):
        return self.stdoffset + self.dst(dt)
        
    def tzname(self, dt):
        if self.dst(dt):
            return self.dstname
        else:
            return self.stdname

    def dst(self, dt):
        if dt is None or dt.tzinfo is None:
            return ZERO
        assert dt.tzinfo is self

        # US DST Rules
        #
        # This is a simplified (i.e., wrong for a few cases) set of rules for US
        # DST start and end times. For a complete and up-to-date set of DST rules
        # and timezone definitions, visit the Olson Database (or try pytz):
        # http://www.twinsun.com/tz/tz-link.htm
        #
        # In the US, since 2007, DST starts at 2am (standard time) on the second
        # Sunday in March, which is the first Sunday on or after Mar 8.
        dst_start = self.__firstsunday(datetime.datetime(dt.year, 3, 8, 2))
        # 1 am on the first Sunday in November
        dst_end = self.__firstsunday(datetime.datetime(dt.year, 11, 1, 1))
        
        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(hours=0)

#Set Snippet Timezone
SNIPPET_TZ = USTimeZone(-8, "Pacific",  "PST", "PDT")


def time_for_reminder(weeklysnippet):
    #If weekly don't remind on Wed(2) Thu(3)
    today = datetime.datetime.now(SNIPPET_TZ).date()
    intday = today.weekday()
    if (weeklysnippet and intday > 1 and intday < 4):
        return False
    return True    


def date_for_snippet(weeklysnippet):
    if(weeklysnippet):
        return date_for_weekly_snippet()
    else:
        return date_for_daily_snippet()


def date_for_globalconf_snippet():
    return date_for_snippet(not SNIPPET_PERIOD == "daily")


def date_for_weekly_snippet():
    #Return the most recent Monday
    #If its Mon(0) or Tue(1) retrun previous Monday
    today = datetime.datetime.now(SNIPPET_TZ).date()
    intday = today.weekday()
    if (intday <= 1):
        intday += 7
    snippet_day = today - datetime.timedelta(days=intday)
    logging.info("date_for_weekly_snippet = %s", snippet_day)
    return snippet_day


def date_for_daily_snippet():
    #Return today, if weekend -- Sat(5), Sun(6) return previous Friday
    today = datetime.datetime.now(SNIPPET_TZ).date()
    intday = today.weekday()
    snippet_day = today
    if (intday >= 5):
        snippet_day = today - datetime.timedelta(days=intday - 4)
    logging.info("date_for_daily_snippet = %s", snippet_day)
    return snippet_day


def time_for_digest(weekly):
    today = datetime.datetime.now(SNIPPET_TZ).date()
    intday = today.weekday()
    #If weekly, Monday digest
    if (weekly and intday == 0):
        return True
    #If daily, Weekday digest
    elif ((not weekly) and intday < 5):
        return True
    #No digest
    else:    
        return False   


def date_for_retrieval(weeklysnippet):
    if(weeklysnippet):
        return date_for_weekly_retrieval()
    else:
        return date_for_daily_retrieval()


def date_for_globalconf_retrieval():
    return date_for_retrieval(not SNIPPET_PERIOD == "daily")


def date_for_weekly_retrieval():
    #Return the most recent Monday
    #If its Mon(0) or Tue(1) retrun previous Monday
    return date_for_weekly_snippet()


def date_for_daily_retrieval():
    #Return yesterday, if Sun(6), Mon (0) return previous Friday
    today = datetime.datetime.now(SNIPPET_TZ).date()
    intday = today.weekday()
    offset = 1
    if (intday == 0):
        offset = 3
    elif(intday == 6):
        offset = 2
    snippet_day = today - datetime.timedelta(days=offset)
    logging.info("date_for_daily_retrieval = %s", snippet_day)
    return snippet_day
 