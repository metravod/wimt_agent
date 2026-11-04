"""SQLite storage: the whole schema and three tiny query helpers.

One file on disk (DATA_DIR/bot.db) holds everything the bot knows.
Dates are stored as ISO strings ("2026-09-30"), so they compare correctly as text.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id        INTEGER PRIMARY KEY,           -- Telegram user id
    name      TEXT NOT NULL,
    username  TEXT,
    tz        TEXT,                          -- NULL means "use the team time zone"
    is_admin  INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS statuses (
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    status    TEXT NOT NULL,                 -- see team.STATUSES
    PRIMARY KEY (member_id, day)
);

CREATE TABLE IF NOT EXISTS standups (
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    text      TEXT NOT NULL,
    PRIMARY KEY (member_id, day)
);

CREATE TABLE IF NOT EXISTS absences (
    id        INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL,                 -- see team.ABSENCES
    start_day TEXT NOT NULL,
    end_day   TEXT NOT NULL,
    reason    TEXT,
    state     TEXT NOT NULL DEFAULT 'pending' -- pending | approved | rejected | cancelled
);

CREATE TABLE IF NOT EXISTS notes (
    id        INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    text      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    day  TEXT PRIMARY KEY,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat (             -- recent conversation, so the agent remembers context
    id        INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    role      TEXT NOT NULL,                 -- user | assistant
    content   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sent (             -- scheduler marks, so nothing is sent twice
    key TEXT PRIMARY KEY
);
"""

conn: sqlite3.Connection


def connect(path) -> None:
    global conn
    conn = sqlite3.connect(path, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'members'").fetchone():
        migrate()
    conn.executescript(SCHEMA)  # creates whatever is missing: everything for a new database
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS)}")


# How the schema changes over time. SCHEMA is always the latest shape, and a new database is
# created straight from it. MIGRATIONS bring an existing database up to date, one step each:
#   - a new table: just add it to SCHEMA;
#   - a new column or index: change SCHEMA *and* append the step, e.g.
#     "ALTER TABLE members ADD COLUMN birthday TEXT".
# Only ever append. The database remembers how many steps it has applied (PRAGMA user_version).
MIGRATIONS: list[str] = []


def migrate() -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRATIONS):
        raise SystemExit(f"The database is newer than this code (schema {version}). Update the bot.")
    for number, step in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.executescript(f"BEGIN; {step}; PRAGMA user_version = {number}; COMMIT;")


def q(sql: str, *args) -> list[sqlite3.Row]:
    return conn.execute(sql, args).fetchall()


def one(sql: str, *args) -> sqlite3.Row | None:
    return conn.execute(sql, args).fetchone()


def run(sql: str, *args) -> sqlite3.Cursor:
    """Execute a write; the cursor tells .rowcount and .lastrowid."""
    return conn.execute(sql, args)
