# Town Square

Collects events from student organizations' public Google Calendars into a Postgres database and serves them as a read-only JSON API through [PostgREST](https://postgrest.org).

```
Google Calendar (.ics) ──▶ main.py ──▶ Postgres (Docker) ──▶ PostgREST ──▶ frontend
                          (importer role)                   (web_anon role, read-only)
```

- **`main.py`** downloads each calendar and stores every event in the `events` table. Recurring events are expanded into one row per occurrence for the next 365 days.
- **`db.py`** holds the database connection, the table schema and the queries.
- **`initdb/`** contains scripts Postgres runs once when the database is first created. They set up the roles below.
- **`postgrest.conf`** configures PostgREST.

## Requirements

- Python 3.14+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- PostgREST 
```sh
brew install postgrest
```

## Setup

### 

1. Clone the repo and cd into it

```sh
git clone https://github.com/komrade-xiatthew/Town-Square
```

1. Install Python dependencies

```sh
python3 -m venv venv
venv/bin/pip install icalendar recurring-ical-events "psycopg[binary]"
```

### 2. Start the database

The `.sh` scripts in `initdb/` must be executable. If they aren't, the container exits on its first start with `Permission denied`:

```sh
chmod +x initdb/*.sh
```

Start Postgres, choosing your own passwords:

```sh
docker run -d --name townsquare-db \
  -p 127.0.0.1:5433:5432 \
  -e POSTGRES_PASSWORD=<admin password> \
  -e IMPORTER_PASSWORD=<importer password> \
  -e READER_PASSWORD=<reader password> \
  -v "$PWD/initdb:/docker-entrypoint-initdb.d:ro" \
  -v townsquare-pgdata:/var/lib/postgresql \
  postgres:18
```

Check the container's logs for `CREATE ROLE` lines to confirm the setup scripts ran.

#### Using Docker Desktop instead of `docker run`

You still need to run the `chmod` command above first.

1. **Get the image.** In the search bar at the top of Docker Desktop, search for `postgres`, choose the official image, set the tag to `18` and click **Pull**.
2. **Create the data volume.** Go to **Volumes → Create**, name it `townsquare-pgdata` and click **Create**.
3. **Open the run dialog.** Go to **Images**, find `postgres:18` and click **Run** (▶). Expand **Optional settings**.
4. **Fill in the settings:**

   | Field | Value |
   |---|---|
   | Container name | `townsquare-db` |
   | Ports → Host port (for `5432/tcp`) | `5433` |
   | Volumes → Host path / Container path | `townsquare-pgdata` → `/var/lib/postgresql` |
   | Volumes → Host path / Container path | full path to this repo's `initdb` folder (click **…** to browse) → `/docker-entrypoint-initdb.d` |
   | Environment variables | `POSTGRES_PASSWORD` = admin password |
   | | `IMPORTER_PASSWORD` = importer password |
   | | `READER_PASSWORD` = reader password |

   Click **+** next to Volumes and Environment variables to add more rows.
5. Click **Run**. Docker Desktop opens the container's **Logs** tab. Look for the `CREATE ROLE` lines.

Later, start and stop the database from the **Containers** tab with the ▶ / ■ buttons. Don't click **Run** on the image again; that creates a second container.

> Docker Desktop's port field publishes the port on all network interfaces, not only `127.0.0.1` as the `docker run` command does. Other devices on your network can then reach the database on port 5433, so use strong passwords, or use the `docker run` command if that matters.

To start over (see the note below), delete the container from **Containers** and the volume from **Volumes**.

> **The `initdb/` scripts only run when the database is created for the first time.** Editing them later has no effect on an existing database. Either apply the change by hand with `psql`, or delete the container *and* its volume (`docker rm -f townsquare-db && docker volume rm townsquare-pgdata`) and start again. Deleting the volume erases all stored events, but `main.py` can re-import them.

### 3. Point the code at the database

The passwords in these files must match the ones used when the database was created:

| File | Setting | Role |
|---|---|---|
| `db.py` | `DATABASE_URL` | `importer` (`IMPORTER_PASSWORD`) |
| `postgrest.conf` | `db-uri` | `authenticator` (password set in `initdb/02-schema.sql`) |

## Usage

### Import events

```sh
venv/bin/python main.py
```

It prints how many events it stored for each organization. On the first run this also creates the `events` table. Run the script regularly, e.g. daily with cron, to pick up changes and keep the 365-day window moving forward.

On each run, a calendar's events from today onward are deleted and re-imported, so cancelled or moved events disappear. Past events are kept.

### Add a calendar

Add an entry to `calendars` in `main.py`. The key is the organization's display name, and the value is the calendar's public iCal address. You can find that address in Google Calendar under **Settings → (calendar) → Integrate calendar → Public address in iCal format**. The calendar must be public.

### Serve the API

```sh
postgrest postgrest.conf
```

The API runs at `http://localhost:3000`. Examples:

```sh
# All upcoming events, soonest first
curl "localhost:3000/events?order=start_time"

# Events on one day (Eastern time; %2D is "-")
curl "localhost:3000/events?start_time=gte.2026-10-12T00:00:00%2D04:00&start_time=lt.2026-10-13T00:00:00%2D04:00"

# Selected fields from one organization
curl "localhost:3000/events?select=summary,start_time,location&organization=eq.TPUSA%20at%20CMU"
```

From a browser, use `fetch` instead of `curl`:

```js
const events = await (await fetch("http://localhost:3000/events?order=start_time")).json();
```

Times are returned in UTC.

## The `events` table

| Column | Description |
|---|---|
| `organization` | Display name from `calendars` in `main.py` |
| `calendar_url` | iCal address the event came from |
| `uid` | Calendar event ID; shared by every occurrence of a recurring event |
| `summary` | Event title |
| `start_time`, `end_time` | Start and end of this occurrence |
| `location` | Free-text location, if set |
| `description` | Event description, if set. It may contain HTML from Google Calendar. |

Each row is unique on `(uid, start_time)`.

## Database roles

| Role | Used by | Access |
|---|---|---|
| `postgres` | You, for admin tasks | Everything |
| `importer` | `main.py` | Creates and writes the `events` table |
| `reader` | Any server-side code that only reads | `SELECT` on tables created by `importer` |
| `authenticator` | PostgREST's login | Nothing on its own; switches to `web_anon` |
| `web_anon` | Every PostgREST request | Read-only access to **every table** (`pg_read_all_data`) |

Because `web_anon` can read everything, any table you add to this database is public through the API. Don't store private data here without first narrowing `web_anon`'s grants.

## Troubleshooting

| Error | Cause |
|---|---|
| `Connection refused` on port 5433 | The database container isn't running. Check `docker ps -a` and the container's logs. |
| Container exits with code 126 / `Permission denied` | An `initdb/*.sh` script isn't executable. See step 2. |
| `password authentication failed for user "importer"` | The role doesn't exist, often because the init scripts were skipped, or the password in `db.py` doesn't match. |
| PostgREST: `Could not find the table ... in the schema cache` | PostgREST loaded its schema before the table existed. Restart it, or run `NOTIFY pgrst, 'reload schema';` in the database. |
