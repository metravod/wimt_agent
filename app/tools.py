"""Everything the agent can do — and nothing else.

Each tool is a plain function. The model sees its name, docstring and parameters.
The first parameter, `me`, is who is talking: it is filled in by the code, never by
the model, so nobody can act as someone else. Tools marked admin=True are not even
shown to regular members.
"""
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import get_type_hints
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ValidationError, create_model

from app import bot, db, reports, team
from app.team import Absence, Member, Status
from app.texts import LANGUAGES, t

log = logging.getLogger(__name__)


class Refused(Exception):
    """A request the tool won't carry out; the message goes back to the model."""


@dataclass
class Tool:
    fn: Callable
    params: type[BaseModel]
    admin: bool
    reads: bool  # only looks things up, changes and sends nothing


TOOLS: dict[str, Tool] = {}


def tool(admin: bool = False, reads: bool = False):
    def register(fn):
        hints = get_type_hints(fn)
        params = list(inspect.signature(fn).parameters.values())[1:]  # skip `me`
        fields = {p.name: (hints[p.name], ... if p.default is p.empty else p.default) for p in params}
        TOOLS[fn.__name__] = Tool(fn, create_model(fn.__name__, **fields), admin, reads)
        return fn
    return register


def schemas(me: Member) -> list[dict]:
    """Tool descriptions for the model, in the OpenAI function-calling format."""
    return [{"type": "function", "function": {
        "name": name, "description": inspect.getdoc(spec.fn), "parameters": spec.params.model_json_schema(),
    }} for name, spec in TOOLS.items() if me.is_admin or not spec.admin]


async def call(me: Member, name: str, arguments: str) -> str:
    spec = TOOLS.get(name)
    if not spec or (spec.admin and not me.is_admin):
        return f"Error: there is no tool {name}."
    try:
        params = spec.params.model_validate_json(arguments or "{}")
        result = spec.fn(me, **dict(params))
        return await result if inspect.isawaitable(result) else result
    except (ValidationError, Refused) as e:
        return f"Error: {e}"
    except Exception:
        log.exception("tool %s failed", name)
        return "Error: internal failure, tell the user to try again later."


def _member(member_id: int) -> Member:
    if who := team.member(member_id):
        return who
    raise Refused(f"no team member with id {member_id}")


# ── where people are ───────────────────────────────────────────────────

@tool()
def set_status(me: Member, status: Status, day: date | None = None, member_id: int | None = None) -> str:
    """Set where someone works on a day (default: today). Leave member_id empty for yourself;
    setting it for someone else is for admins. For vacation or sick leave spanning days, use request_absence."""
    who = _member(member_id) if member_id else me
    if who.id != me.id and not me.is_admin:
        raise Refused("only admins can set someone else's status")
    day = day or who.today()
    db.run("INSERT INTO statuses (member_id, day, status) VALUES (?, ?, ?) "
           "ON CONFLICT DO UPDATE SET status = excluded.status", who.id, day.isoformat(), status)
    return f"{who.name}: {status} on {day}."


@tool(reads=True)
def team_day(me: Member, day: date | None = None) -> str:
    """Who is where on a day (default: today), with everyone's standup for that day."""
    day = day or me.today()
    lines = [f"{day:%A %Y-%m-%d}: {team.day_off(day) or 'workday'}"]
    for m in team.members():
        lines.append(f"- {m.name}: {team.status(m.id, day) or 'no status'}, "
                     f"standup: {team.standup(m.id, day) or 'not sent'}")
    return "\n".join(lines)


# ── standups, notes, reports ───────────────────────────────────────────

@tool()
def save_standup(me: Member, text: str, day: date | None = None) -> str:
    """Save your standup for a day (default: today): what was done, what's planned, blockers.
    Replaces an earlier standup for that day, so to add to it pass the combined text.
    Keep the author's words; tidy up only the form."""
    day = day or me.today()
    db.run("INSERT INTO standups (member_id, day, text) VALUES (?, ?, ?) "
           "ON CONFLICT DO UPDATE SET text = excluded.text", me.id, day.isoformat(), text)
    return f"Standup saved for {day}."


@tool(reads=True)
def read_standups(me: Member, start: date, end: date, member_id: int | None = None) -> str:
    """Standups of the whole team, or of one member, for a period (dates inclusive)."""
    return reports.standups(start, end, member_id)[-60_000:] or "No standups in this period."


@tool(reads=True)
def read_summary(me: Member, day: date) -> str:
    """The standup summary that was sent to the team on a day."""
    row = db.one("SELECT text FROM summaries WHERE day = ?", day.isoformat())
    return row["text"] if row else "No summary for this day."


@tool()
async def send_retro(me: Member, start: date, end: date) -> str:
    """Write a retrospective of the team's standups over a period and send it to the user
    as a separate message. Use it for "retro", "how did the sprint/month go" and the like."""
    text = await reports.analysis("retro", start, end)
    if not text:
        return "No standups in this period, nothing to analyse."
    await bot.send(me.id, text)
    return "The retro was sent as a separate message; don't repeat it."


@tool()
def add_note(me: Member, text: str) -> str:
    """Save a private note for today — only its author can read it. Handy for jotting down work to recall at standup."""
    db.run("INSERT INTO notes (member_id, day, text) VALUES (?, ?, ?)", me.id, me.today().isoformat(), text)
    return "Note saved."


@tool(reads=True)
def read_notes(me: Member, start: date, end: date) -> str:
    """Your own private notes for a period (dates inclusive)."""
    rows = db.q("SELECT day, text FROM notes WHERE member_id = ? AND day BETWEEN ? AND ? ORDER BY id",
                me.id, start.isoformat(), end.isoformat())
    return "\n".join(f"{r['day']}: {r['text']}" for r in rows) or "No notes in this period."


# ── absences ───────────────────────────────────────────────────────────

@tool()
async def request_absence(me: Member, kind: Absence, start: date, end: date, reason: str | None = None,
                          member_id: int | None = None) -> str:
    """Request vacation, sick leave or a day off (dates inclusive). Leave member_id empty for yourself;
    recording an absence for someone else is for admins. Admins' requests are approved at once,
    members' requests go to the admins for approval."""
    who = _member(member_id) if member_id else me
    if who.id != me.id and not me.is_admin:
        raise Refused("only admins can request an absence for someone else")
    if end < start:
        raise Refused("the end date is before the start date")
    state = "approved" if me.is_admin else "pending"
    absence_id = db.run("INSERT INTO absences (member_id, kind, start_day, end_day, reason, state) "
                        "VALUES (?, ?, ?, ?, ?, ?)", who.id, kind, start.isoformat(), end.isoformat(),
                        reason, state).lastrowid
    if state == "approved":
        if who.id != me.id:
            await bot.send(who.id, t("absence_decided", kind=t(kind), start=start, end=end, state=t("approved")))
        return f"Absence #{absence_id} for {who.name} recorded and approved."
    text = t("absence_ask", name=me.name, kind=t(kind), start=start, end=end, reason=f"\n{reason}" if reason else "")
    markup = bot.buttons([(t("approve"), f"absence:{absence_id}:approved"),
                          (t("reject"), f"absence:{absence_id}:rejected")])
    for admin in team.admins():
        await bot.send(admin.id, text, markup)
    return f"Request #{absence_id} sent to the admins for approval."


@tool()
def cancel_absence(me: Member, absence_id: int) -> str:
    """Cancel one of your own absence requests, pending or approved."""
    cancelled = db.run("UPDATE absences SET state = 'cancelled' WHERE id = ? AND member_id = ? "
                       "AND state IN ('pending', 'approved')", absence_id, me.id).rowcount
    if not cancelled:
        raise Refused(f"you have no active request #{absence_id}")
    return f"Request #{absence_id} cancelled."


@tool(reads=True)
def list_absences(me: Member, start: date, end: date) -> str:
    """Absences overlapping a period: approved ones of the whole team, and pending ones
    (all of them for admins, only your own otherwise). Shows the ids used to cancel or decide."""
    rows = db.q("SELECT a.*, m.name FROM absences a JOIN members m ON m.id = a.member_id "
                "WHERE a.start_day <= ? AND a.end_day >= ? AND a.state IN ('approved', 'pending') "
                "ORDER BY a.start_day", end.isoformat(), start.isoformat())
    return "\n".join(
        f"#{r['id']} {r['name']}: {r['kind']} {r['start_day']} – {r['end_day']}, {r['state']}"
        + (f" ({r['reason']})" if r["reason"] else "")
        for r in rows if r["state"] == "approved" or me.is_admin or r["member_id"] == me.id
    ) or "No absences in this period."


async def decide(absence_id: int, state: str) -> str:
    """Approve or reject a pending request and tell its author. Also used by the buttons."""
    row = db.one("SELECT * FROM absences WHERE id = ? AND state = 'pending'", absence_id)
    if not row or state not in ("approved", "rejected"):
        raise Refused(f"no pending request #{absence_id}")
    db.run("UPDATE absences SET state = ? WHERE id = ?", state, absence_id)
    await bot.send(row["member_id"], t("absence_decided", kind=t(row["kind"]), start=row["start_day"],
                                       end=row["end_day"], state=t(state)))
    return f"Request #{absence_id} {state}; its author was notified."


@tool(admin=True)
async def decide_absence(me: Member, absence_id: int, approve: bool) -> str:
    """Approve or reject a pending absence request."""
    return await decide(absence_id, "approved" if approve else "rejected")


# ── settings and people ────────────────────────────────────────────────

def _check_tz(tz: str) -> str:
    try:
        ZoneInfo(tz)
        return tz
    except (ZoneInfoNotFoundError, ValueError):
        raise Refused(f"unknown time zone {tz!r}, use an IANA name like Europe/Berlin") from None


@tool()
def set_my_timezone(me: Member, tz: str) -> str:
    """Set your own time zone, if it differs from the team's (IANA name, e.g. "Asia/Tbilisi")."""
    db.run("UPDATE members SET tz = ? WHERE id = ?", _check_tz(tz), me.id)
    return f"Your time zone is now {tz}."


@tool(admin=True)
def update_settings(me: Member, tz: str | None = None, country: str | None = None, language: str | None = None,
                    status_time: str | None = None, standup_time: str | None = None,
                    summary_time: str | None = None) -> str:
    """Change team settings. Pass EVERY setting the user mentioned, all in one call.
    tz: the team's IANA time zone ("Europe/Berlin"). country: ISO code for public holidays ("DE", "RU").
    When the user names a city, set both tz and that city's country, even if a country was set before:
    "we're in Berlin" -> tz="Europe/Berlin", country="DE". Only if the user asks to ignore public holidays,
    pass country="" and nothing else.
    language: of the bot's scheduled messages, one of: en, ru.
    status_time / standup_time: when to ask for statuses and standups; summary_time: the standup
    summary deadline. Times are "HH:MM", local."""
    changes = {k: v for k, v in [("tz", tz), ("country", country), ("language", language),
               ("status_time", status_time), ("standup_time", standup_time), ("summary_time", summary_time)]
               if v is not None}
    if changes.get("country") == "" and len(changes) > 1:  # a filled-in blank, or holidays would silently go off
        raise Refused('country="" turns public holidays off: pass the ISO code, or leave country out')
    if "tz" in changes and "country" not in changes and not team.setting("country"):  # holidays would stay off unseen
        raise Refused("public holidays are off: pass the country's ISO code together with tz")
    for key, value in changes.items():  # validate everything before saving anything
        if key == "tz":
            _check_tz(value)
        if key == "country" and value:
            changes[key] = value = value.upper()
            try:
                team.country_holidays(value, date.today().year)
            except NotImplementedError:
                raise Refused(f"unknown country code {value!r}")
        if key == "language" and value not in LANGUAGES:
            raise Refused(f"supported languages: {', '.join(LANGUAGES)}")
        if key.endswith("_time"):
            try:
                changes[key] = datetime.strptime(value, "%H:%M").strftime("%H:%M")
            except ValueError:
                raise Refused(f"{key} must look like 09:30")
    for key, value in changes.items():
        team.set_setting(key, value)
    unchanged = [f"{k}={team.setting(k)}" for k in team.DEFAULTS if k not in changes]
    return (f"Changed only: {', '.join(f'{k}={v}' for k, v in changes.items()) or 'nothing'}. "
            f"Unchanged: {', '.join(unchanged)}.")


@tool(admin=True)
def set_admin(me: Member, member_id: int, is_admin: bool) -> str:
    """Give a member admin rights, or take them away."""
    who = _member(member_id)
    if who.is_admin and not is_admin and len(team.admins()) == 1:
        raise Refused("the team needs at least one admin")
    db.run("UPDATE members SET is_admin = ? WHERE id = ?", is_admin, who.id)
    return f"{who.name} is {'now' if is_admin else 'no longer'} an admin."


@tool(admin=True)
async def remove_member(me: Member, member_id: int) -> str:
    """Remove a member from the team with all their data. Sends the admin a confirmation button;
    nothing is deleted until they press it."""
    who = _member(member_id)
    if who.id == me.id:
        raise Refused("you can't remove yourself")
    await bot.send(me.id, t("remove_ask", name=who.name),
                   bot.buttons([(t("remove"), f"remove:{who.id}"), (t("cancel"), "remove:cancel")]))
    return f"NOT removed yet: {me.name} got a button to confirm removing {who.name}."


def remove(member_id: int) -> str:
    """Delete a member and their data; called by the confirmation button, never by the model."""
    who = _member(member_id)
    db.run("DELETE FROM members WHERE id = ?", who.id)
    return who.name


@tool(admin=True)
async def announce(me: Member, text: str) -> str:
    """Send a message from you to every other team member."""
    others = [m for m in team.members() if m.id != me.id]
    for m in others:
        await bot.send(m.id, f"📣 {me.name}:\n{text}")
    return f"Sent to {len(others)} people."
