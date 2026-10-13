import os

import psycopg

# e.g. postgresql://user:password@localhost:5432/townsquare
#DATABASE_URL = "postgresql://postgres@localhost:5432"
DATABASE_URL = "postgresql://importer:importer@localhost:5433/postgres"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    organization   text        NOT NULL,
    calendar_url   text        NOT NULL,
    -- Shared by every occurrence of a recurring event
    uid            text        NOT NULL,
    summary        text,
    start_time     timestamptz NOT NULL,
    end_time       timestamptz,
    location       text,
    description    text,
    UNIQUE (uid, start_time)
)
"""

# Columns added after the table was first created
ADD_COLUMNS = "ALTER TABLE events ADD COLUMN IF NOT EXISTS description text"

CREATE_INDEX = "CREATE INDEX IF NOT EXISTS events_start_time ON events (start_time)"

UPSERT_EVENT = """
INSERT INTO events (organization, calendar_url, uid, summary, start_time, end_time,
                    location, description)
VALUES (%(organization)s, %(calendar_url)s, %(uid)s, %(summary)s, %(start_time)s,
        %(end_time)s, %(location)s, %(description)s)
ON CONFLICT (uid, start_time) DO UPDATE SET
    organization = EXCLUDED.organization,
    calendar_url = EXCLUDED.calendar_url,
    summary      = EXCLUDED.summary,
    end_time     = EXCLUDED.end_time,
    location     = EXCLUDED.location,
    description  = EXCLUDED.description
"""


def connect():
    return psycopg.connect(DATABASE_URL)


def create_tables(conn):
    conn.execute(CREATE_TABLE)
    conn.execute(ADD_COLUMNS)
    conn.execute(CREATE_INDEX)


def save_event(conn, event):
    """Insert an event, or update it if it's already stored.

    `event` is a dict with the same keys as the events table's columns.
    """
    conn.execute(UPSERT_EVENT, event)


def delete_events_from(conn, calendar_url, start):
    """Delete a calendar's stored events starting at or after `start`.

    Called before re-importing that window, so occurrences that were cancelled
    or moved don't linger. Events before `start` are kept as history.
    """
    conn.execute(
        "DELETE FROM events WHERE calendar_url = %s AND start_time >= %s",
        (calendar_url, start),
    )
