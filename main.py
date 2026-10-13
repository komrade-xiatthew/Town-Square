import datetime
import urllib.request
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

import db

calendars = {"Evil Commie Scum": "https://calendar.google.com/calendar/ical/c_822b49ac86209308706d81f9e4b4c016617f274f477333f385e81d2c525b4921%40group.calendar.google.com/public/basic.ics",
             "TPUSA at CMU" : "https://calendar.google.com/calendar/ical/c_0d7ff44ca21cb1a0f4df31e00a51b95949e2fdc7e398868457d49f9a987cfb3d%40group.calendar.google.com/public/basic.ics"}

# Recurring events are expanded into individual occurrences within this window.
DAYS_AHEAD = 365
TIMEZONE = ZoneInfo("America/New_York")


def fetch_calendar(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return icalendar.Calendar.from_ical(resp.read())


today = datetime.datetime.now(TIMEZONE).date()
window_start = datetime.datetime.combine(today, datetime.time(), tzinfo=TIMEZONE)
window_end = window_start + datetime.timedelta(days=DAYS_AHEAD)

with db.connect() as conn:
    db.create_tables(conn)

    for org, cal_url in calendars.items():
        cal = fetch_calendar(cal_url)

        # Re-import the whole window so cancelled or moved occurrences are dropped
        db.delete_events_from(conn, cal_url, window_start)

        count = 0
        # Yields one VEVENT per occurrence, with edited occurrences and
        # cancellations (EXDATE) already applied.
        for event in recurring_ical_events.of(cal).between(window_start, window_end):
            db.save_event(conn, {
                "calendar_url": cal_url,
                "organization": org,
                "uid": str(event["UID"]),
                "summary": str(event.get("SUMMARY", "")),
                "start_time": event.decoded("DTSTART"),
                "end_time": event.decoded("DTEND") if "DTEND" in event else None,
                "location": str(event["LOCATION"]) if "LOCATION" in event else None,
                "description": str(event["DESCRIPTION"]) if "DESCRIPTION" in event else None,
            })
            count += 1

        print(f"Stored {count} events from {org}")
