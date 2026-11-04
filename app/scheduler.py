"""The daily rhythm: morning pings, reminders, the standup summary, the weekly review.

Deterministic on purpose — this is a clock, not an agent. It wakes up every minute;
each message is marked in the `sent` table, so restarts never cause duplicates.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app import bot, db, reports, team
from app.team import Member
from app.texts import t

log = logging.getLogger(__name__)
HOUR = timedelta(hours=1)
HOLIDAY_WARNING_TIME = "16:00"


async def run() -> None:
    while True:
        try:
            await tick()
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(60)


async def tick() -> None:
    for m in team.members():
        await pings(m)
        await holiday_warning(m)
    await summary()
    await weekly()


def once(key: str) -> bool:
    """True the first time a key is seen, False ever after."""
    return db.run("INSERT OR IGNORE INTO sent (key) VALUES (?)", key).rowcount == 1


def due(now: datetime, at: str, shift: timedelta = timedelta()) -> bool:
    """Is it the hour starting at local time `at` ("HH:MM") + shift? Missed longer ago = skipped."""
    start = datetime.combine(now.date(), datetime.strptime(at, "%H:%M").time(), now.tzinfo) + shift
    return start <= now < start + HOUR


def status_buttons():
    return bot.buttons(*[[(t(s), f"status:{s}") for s in row] for row in (team.STATUSES[:3], team.STATUSES[3:])])


async def pings(m: Member) -> None:
    """Ask a member for their status and standup, in their own time zone, on working days."""
    now = m.now()
    day = now.date()
    if team.day_off(day) or team.away(m.id, day):
        return
    key = f"{day}:{m.id}"
    status_time = team.setting("status_time")
    if not team.status(m.id, day):
        if due(now, status_time) and once(f"status_ask:{key}"):
            await bot.send(m.id, t("status_ask"), status_buttons())
        elif due(now, status_time, HOUR) and once(f"status_remind:{key}"):
            await bot.send(m.id, t("status_remind"), status_buttons())
    summary_time = team.setting("summary_time")
    if not team.standup(m.id, day) and not db.one("SELECT 1 FROM summaries WHERE day = ?", day.isoformat()):
        if due(now, team.setting("standup_time")) and once(f"standup_ask:{key}"):
            await bot.send(m.id, t("standup_ask"))
        elif due(now, summary_time, -HOUR) and once(f"standup_remind:{key}"):
            await bot.send(m.id, t("standup_remind", time=summary_time))


async def holiday_warning(m: Member) -> None:
    """On the last working day before a holiday, say the bot goes quiet. A plain weekend needs no warning."""
    now = m.now()
    day = now.date()
    if team.day_off(day) or team.away(m.id, day) or not due(now, HOLIDAY_WARNING_TIME):
        return
    if (ahead := team.holiday_ahead(day)) and once(f"holiday_warning:{day}:{m.id}"):
        first, name, back = ahead
        await bot.send(m.id, t("holiday_warning", name=name, day=f"{first:%d.%m}", back=f"{back:%d.%m}"))


async def summary() -> None:
    """Send the standup summary once everyone present has reported, or at the deadline."""
    now = team.team_now()
    day = now.date()
    if team.day_off(day) or db.one("SELECT 1 FROM summaries WHERE day = ?", day.isoformat()):
        return
    present = [m for m in team.members() if not team.away(m.id, day)]
    reported = [m for m in present if team.standup(m.id, day)]
    deadline = now.strftime("%H:%M") >= team.setting("summary_time")
    if not reported or (len(reported) < len(present) and not deadline):
        return
    text = await reports.daily_summary(day)  # if the model fails, the next tick retries
    db.run("INSERT INTO summaries (day, text) VALUES (?, ?)", day.isoformat(), text)
    for m in present:
        await bot.send(m.id, t("summary", day=day, text=text))


async def weekly() -> None:
    """On the week's first working day after the summary deadline: last week's review to admins, and a personal
    one to each member. Each review is marked only once it went out, so one the model failed on is retried on the
    next tick."""
    now = team.team_now()
    if not team.first_workday_of_week(now.date()) or now.strftime("%H:%M") < team.setting("summary_time"):
        return
    monday = now.date() - timedelta(days=now.weekday())
    start, end = monday - timedelta(days=7), monday - timedelta(days=1)
    reviews = [(f"weekly:{now.date()}", "weekly_team", None, team.admins())]
    reviews += [(f"weekly:{now.date()}:{m.id}", "weekly_personal", m.id, [m]) for m in team.members()]
    for key, kind, member_id, readers in reviews:
        if db.one("SELECT 1 FROM sent WHERE key = ?", key):
            continue
        try:
            text = await reports.analysis(kind, start, end, member_id)
        except Exception:
            log.exception("%s review failed, retrying on the next tick", kind)
            continue
        for reader in readers if text else []:
            await bot.send(reader.id, t(kind, text=text))
        once(key)
