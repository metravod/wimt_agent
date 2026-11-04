"""The team: members, settings and the calendar.

Plain functions over the database, shared by the agent's tools and the scheduler.
"""
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Literal, get_args
from zoneinfo import ZoneInfo

import holidays

from app import db

Status = Literal["office", "remote", "travel", "day_off", "vacation", "sick"]
Absence = Literal["vacation", "sick", "day_off"]  # an approved absence also sets the day's status
STATUSES = get_args(Status)
ABSENCES = get_args(Absence)

DEFAULTS = {
    "language": "en",         # language of scheduled messages; the agent mirrors whoever writes to it
    "tz": "UTC",              # team time zone, members can override their own
    "country": "",            # ISO code for public holidays ("RU", "DE", ...); empty = weekends only
    "status_time": "09:00",   # ask everyone where they are
    "standup_time": "10:00",  # ask for the daily standup
    "summary_time": "12:00",  # summary deadline: sent earlier if everyone has reported
}


# ── settings ───────────────────────────────────────────────────────────

def setting(key: str) -> str:
    row = db.one("SELECT value FROM settings WHERE key = ?", key)
    return row["value"] if row else DEFAULTS[key]


def set_setting(key: str, value: str) -> None:
    db.run("INSERT INTO settings (key, value) VALUES (?, ?) "
           "ON CONFLICT (key) DO UPDATE SET value = excluded.value", key, value)


def invite_code() -> str:
    row = db.one("SELECT value FROM settings WHERE key = 'invite'")
    if row:
        return row["value"]
    code = secrets.token_urlsafe(9)
    set_setting("invite", code)
    return code


# ── members ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Member:
    id: int
    name: str
    username: str | None
    tz: str | None
    is_admin: bool

    def now(self) -> datetime:
        return datetime.now(ZoneInfo(self.tz or setting("tz")))

    def today(self) -> date:
        return self.now().date()


def _member(row) -> Member:
    return Member(row["id"], row["name"], row["username"], row["tz"], bool(row["is_admin"]))


def members() -> list[Member]:
    return [_member(r) for r in db.q("SELECT * FROM members ORDER BY name")]


def member(member_id: int) -> Member | None:
    row = db.one("SELECT * FROM members WHERE id = ?", member_id)
    return _member(row) if row else None


def admins() -> list[Member]:
    return [m for m in members() if m.is_admin]


def add_member(member_id: int, name: str, username: str | None, is_admin: bool = False) -> Member:
    db.run("INSERT INTO members (id, name, username, is_admin) VALUES (?, ?, ?, ?)",
           member_id, name, username, is_admin)
    return member(member_id)


# ── calendar ───────────────────────────────────────────────────────────

def team_now() -> datetime:
    return datetime.now(ZoneInfo(setting("tz")))


@lru_cache
def country_holidays(country: str, year: int):
    return holidays.country_holidays(country, years=year)


def day_off(day: date) -> str | None:
    """Why nobody works this day ("weekend" or a holiday name), or None for a workday."""
    if day.weekday() >= 5:
        return "weekend"
    country = setting("country")
    return country_holidays(country, day.year).get(day) if country else None


def holiday_ahead(day: date) -> tuple[date, str, date] | None:
    """Is a holiday next, weekends aside? (its date, its name, the day work resumes), or None."""
    first = day + timedelta(days=1)
    while day_off(first) == "weekend":
        first += timedelta(days=1)
    name = day_off(first)
    if not name:
        return None
    back = first
    while day_off(back):
        back += timedelta(days=1)
    return first, name, back


def first_workday_of_week(day: date) -> bool:
    monday = day - timedelta(days=day.weekday())
    return not day_off(day) and all(day_off(monday + timedelta(days=i)) for i in range(day.weekday()))


# ── what is known about a member on a given day ────────────────────────

def absence(member_id: int, day: date):
    return db.one("SELECT * FROM absences WHERE member_id = ? AND state = 'approved' "
                  "AND start_day <= ? AND end_day >= ?", member_id, day.isoformat(), day.isoformat())


def status(member_id: int, day: date) -> str | None:
    """An approved absence wins over a status set that day (morning "office", then fell ill)."""
    if away := absence(member_id, day):
        return away["kind"]
    row = db.one("SELECT status FROM statuses WHERE member_id = ? AND day = ?", member_id, day.isoformat())
    return row["status"] if row else None


def away(member_id: int, day: date) -> str | None:
    """"vacation" / "sick" / "day_off" if the member is not working that day, else None."""
    s = status(member_id, day)
    return s if s in ABSENCES else None


def standup(member_id: int, day: date) -> str | None:
    row = db.one("SELECT text FROM standups WHERE member_id = ? AND day = ?", member_id, day.isoformat())
    return row["text"] if row else None
