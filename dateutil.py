import datetime

class Eastern_tzinfo(datetime.tzinfo):
    """Implementation of the Eastern timezone.
    
    Adapted from http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html
    """
    def utcoffset(self, dt):
        return datetime.timedelta(hours=-5) + self.dst(dt)

    def _FirstSunday(self, dt):
        """First Sunday on or after dt."""
        return dt + datetime.timedelta(days=(6-dt.weekday()))

    def dst(self, dt):
        # 2 am on the second Sunday in March
        dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
        # 1 am on the first Sunday in November
        dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(hours=0)
        
    def tzname(self, dt):
        if self.dst(dt) == datetime.timedelta(hours=0):
            return "EST"
        else:
            return "EDT"
        
class Pacific_tzinfo(datetime.tzinfo):
    """Implementation of the Pacific timezone.
    
    Adapted from http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html
    """
    def utcoffset(self, dt):
        return datetime.timedelta(hours=-8) + self.dst(dt)

    def _FirstSunday(self, dt):
        """First Sunday on or after dt."""
        return dt + datetime.timedelta(days=(6-dt.weekday()))

    def dst(self, dt):
        # 2 am on the second Sunday in March
        dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
        # 1 am on the first Sunday in November
        dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(hours=0)
        
    def tzname(self, dt):
        if self.dst(dt) == datetime.timedelta(hours=0):
            return "PST"
        else:
            return "PDT"
        
def date_for_new_snippet():
    """Return previous Monday"""
    today = datetime.datetime.now(Pacific_tzinfo()).date()
    aligned = today - datetime.timedelta(days=today.weekday())
    return aligned

def date_for_retrieval():
    """Always return the most recent Monday."""
    today = datetime.datetime.now(Pacific_tzinfo()).date()
    return today - datetime.timedelta(days=today.weekday())
    
    
def date_for_daily_snippet():
    """Return today, if weekend -- Sat(5), Sun(6) return previous friday."""
    today = datetime.datetime.now(Pacific_tzinfo()).date()
    snippet_day = today
    if (today.weekday() >= 5):
        snippet_day = today - datetime.timedelta(days=(today.weekday() - 4))
    
    return snippet_day
        
def date_for_daily_retrieval():
    """Return yesterday, if monday (0) return previous friday."""
    today = datetime.datetime.now(Pacific_tzinfo()).date()
    if (today.weekday() == 0):
        return today - datetime.timedelta(days=3)
    return today - datetime.timedelta(days=1)
    