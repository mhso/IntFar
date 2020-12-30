from datetime import tzinfo, timedelta, datetime

class TimeZone(tzinfo):
    """
    Class for representing the time zone of Copenhagen (UTC+1).
    """
    def tzname(self, dt):
        return "Europe/Copenhagen"

    def utcoffset(self, dt):
        return self.dst(dt) + timedelta(0, 0, 0, 0, 0, 1, 0)

    def dst(self, dt):
        if dt.month < 10 or dt.month > 3:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        if dt.month == 10 and dt.day < 25:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        if dt.month == 3 and dt.day > 28:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        return timedelta(0, 0, 0, 0, 0, 1, 0)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"
]

def current_month():
    return MONTH_NAMES[datetime.now().month-1]

def zero_pad(number):
    if number < 10:
        return "0" + str(number)
    return str(number)

def round_digits(number):
    if type(number) == float:
        return f"{number:.2f}"
    return str(number)

def format_duration(dt_1, dt_2):
    normed_dt = dt_2.replace(year=dt_1.year, month=dt_1.month)
    month_normed = dt_2.month if dt_2.month >= dt_1.month else dt_2.month + 12
    months = month_normed - dt_1.month
    if normed_dt < dt_1:
        months -= 1
    years = dt_2.year - dt_1.year
    if dt_2.month < dt_1.month:
        years -= 1
    if months == 0 and years == 0:
        td = dt_2 - dt_1
    else:
        td = normed_dt - dt_1
    days = td.days
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    response = f"{zero_pad(hours)}h {zero_pad(minutes)}m {zero_pad(seconds)}s"
    if minutes == 0:
        response = f"{seconds} seconds"
    else:
        response = f"{zero_pad(minutes)} minutes & {zero_pad(seconds)} seconds"
    if hours > 0:
        response = f"{zero_pad(hours)}h {zero_pad(minutes)}m {zero_pad(seconds)}s "
    if days > 0:
        response = f"{days} days, " + response
    if months > 0:
        response = f"{months} months, " + response
    if years > 0:
        response = f"{years} years, " + response
    return response
