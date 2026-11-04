"""Tests with an in-memory database and fake Telegram / model. Run: pytest"""
import asyncio
import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app import agent, bot, db, llm, scheduler, team, tools

MONDAY = date(2026, 9, 28)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    db.connect(":memory:")
    sent = []

    async def send(chat_id, text, markup=None):
        sent.append((chat_id, text))

    monkeypatch.setattr(bot, "send", send)
    monkeypatch.setattr(bot, "username", "team_bot")
    team.add_member(1, "Anna", "anna", is_admin=True)
    team.add_member(2, "Boris", None)
    return sent


def call(who, name, **args):
    return asyncio.run(tools.call(team.member(who), name, json.dumps(args, default=str)))


def tool_call(name, **args):
    fn = SimpleNamespace(name=name, arguments=json.dumps(args, default=str))
    return SimpleNamespace(id=name, function=fn)


def asks(*calls):
    """A model reply that calls tools."""
    return SimpleNamespace(content=None, tool_calls=list(calls), model_dump=lambda **_: {"role": "assistant"})


def test_members_see_no_admin_tools_and_never_the_me_parameter():
    names = lambda m: {s["function"]["name"] for s in tools.schemas(team.member(m))}
    assert "update_settings" in names(1) and "update_settings" not in names(2)
    assert all("me" not in s["function"]["parameters"]["properties"] for s in tools.schemas(team.member(1)))


def test_a_member_cannot_use_admin_tools_or_act_for_others():
    assert call(2, "set_admin", member_id=2, is_admin=True).startswith("Error")
    assert call(2, "set_status", status="office", member_id=1).startswith("Error")
    assert call(1, "set_status", status="office", member_id=2, day=MONDAY) == "Boris: office on 2026-09-28."


def test_bad_arguments_go_back_to_the_model_as_errors():
    assert call(2, "set_status", status="on the moon").startswith("Error")
    assert call(1, "update_settings", tz="Mars/Olympus").startswith("Error")
    assert call(1, "update_settings", status_time="9:5").startswith("Changed only")  # normalised to 09:05
    assert team.setting("status_time") == "09:05"


def test_absence_needs_approval_and_then_counts_as_status(setup):
    reply = call(2, "request_absence", kind="vacation", start=MONDAY, end=MONDAY + timedelta(days=4))
    assert "sent to the admins" in reply and setup[-1][0] == 1
    assert team.away(2, MONDAY) is None
    asyncio.run(tools.decide(1, "approved"))
    assert team.away(2, MONDAY + timedelta(days=2)) == "vacation"
    assert setup[-1][0] == 2  # the author is told
    with pytest.raises(tools.Refused):
        asyncio.run(tools.decide(1, "rejected"))  # already decided


def test_scheduler_asks_once_and_skips_absent_people(setup, monkeypatch):
    monkeypatch.setattr(team.Member, "now", lambda self: datetime(2026, 9, 28, 9, 0, tzinfo=ZoneInfo("UTC")))
    call(1, "set_status", status="sick")
    asyncio.run(scheduler.pings(team.member(1)))
    asyncio.run(scheduler.pings(team.member(2)))
    asyncio.run(scheduler.pings(team.member(2)))
    assert [chat for chat, _ in setup] == [2]


def test_summary_waits_for_everyone_present(setup, monkeypatch):
    now = datetime.combine(MONDAY, datetime.min.time().replace(hour=10), ZoneInfo("UTC"))
    monkeypatch.setattr(team, "team_now", lambda: now)

    async def write(prompt, material):
        return f"summary of: {material}"

    monkeypatch.setattr(llm, "write", write)
    db.run("INSERT INTO standups VALUES (1, ?, 'did X')", MONDAY.isoformat())
    asyncio.run(scheduler.summary())
    assert setup == []  # Boris hasn't reported and it's before the deadline
    db.run("INSERT INTO standups VALUES (2, ?, 'did Y')", MONDAY.isoformat())
    asyncio.run(scheduler.summary())
    assert {chat for chat, _ in setup} == {1, 2} and "did Y" in setup[0][1]


def test_agent_calls_tools_until_it_has_an_answer(monkeypatch):
    replies = iter([
        asks(tool_call("set_status", status="remote"), tool_call("save_standup", text="Fixed login")),
        SimpleNamespace(content="Done: remote, standup saved.", tool_calls=None),
    ])

    async def chat(messages, schemas):
        return next(replies)

    monkeypatch.setattr(llm, "chat", chat)
    reply = asyncio.run(agent.answer(team.member(2), "remote today, fixed login"))
    today = team.member(2).today()
    assert reply == "Done: remote, standup saved."
    assert team.status(2, today) == "remote" and team.standup(2, today) == "Fixed login"
    assert len(db.q("SELECT * FROM chat")) == 2


def test_a_turn_that_breaks_off_after_a_tool_acted_says_and_remembers_what_was_done(setup, monkeypatch):
    replies = iter([asks(tool_call("team_day"), tool_call("request_absence", kind="vacation", start=MONDAY, end=MONDAY))])

    async def chat(messages, schemas):
        if reply := next(replies, None):
            return reply
        raise RuntimeError("the model is unavailable")

    monkeypatch.setattr(llm, "chat", chat)
    reply = asyncio.run(agent.answer(team.member(2), "vacation on Monday"))
    assert setup[-1][0] == 1  # the request reached the admin before the model failed
    assert "Request #1 sent to the admins" in reply and "workday" not in reply  # what was done, not what was read
    history = db.q("SELECT role, content FROM chat ORDER BY id")
    assert [r["role"] for r in history] == ["user", "assistant"] and "Request #1" in history[1]["content"]


def test_messages_of_one_member_are_answered_one_at_a_time(monkeypatch):
    seen, busy = [], {"now": 0, "most": 0}

    async def chat(messages, schemas):
        busy["now"] += 1
        busy["most"] = max(busy["most"], busy["now"])
        seen.append(len(messages))
        await asyncio.sleep(0.01)  # the model takes a while; a second message arrives meanwhile
        busy["now"] -= 1
        return SimpleNamespace(content="ok", tool_calls=None)

    async def two_messages():
        await asyncio.gather(agent.answer(team.member(2), "remote today"), agent.answer(team.member(2), "and sick tomorrow"))

    monkeypatch.setattr(llm, "chat", chat)
    asyncio.run(two_messages())
    assert busy["most"] == 1 and seen == [2, 4]  # the second turn sees the first one in its history


def test_a_weekly_review_the_model_failed_on_goes_out_on_the_next_tick(setup, monkeypatch):
    now = datetime.combine(MONDAY, datetime.min.time().replace(hour=13), ZoneInfo("UTC"))
    monkeypatch.setattr(team, "team_now", lambda: now)
    for member_id in (1, 2):
        db.run("INSERT INTO standups VALUES (?, ?, 'did X')", member_id, (MONDAY - timedelta(days=3)).isoformat())
    model = {"down": True}

    async def write(prompt, material):
        if model["down"] and prompt == "weekly_team":
            raise RuntimeError("the model is unavailable")
        return f"{prompt} review"

    monkeypatch.setattr(llm, "write", write)
    asyncio.run(scheduler.weekly())
    assert [chat for chat, _ in setup] == [1, 2]  # the failed team review holds back nobody's own
    model["down"] = False
    asyncio.run(scheduler.weekly())
    asyncio.run(scheduler.weekly())  # and nothing goes out twice
    team_reviews = [chat for chat, text in setup if "weekly_team review" in text]
    personal = [chat for chat, text in setup if "weekly_personal review" in text]
    assert team_reviews == [1] and personal == [1, 2]


def test_a_blank_country_cannot_slip_in_with_other_settings():
    team.set_setting("country", "RU")
    assert call(1, "update_settings", tz="Europe/Moscow", country="", status_time="07:50").startswith("Error")
    assert (team.setting("country"), team.setting("status_time")) == ("RU", "09:00")
    assert call(1, "update_settings", country="").startswith("Changed only")  # asked for on its own: fine
    assert team.setting("country") == ""


def test_a_time_zone_needs_a_country_while_holidays_are_off():
    team.set_setting("country", "")
    tz = team.setting("tz")
    assert call(1, "update_settings", tz="Europe/Lisbon").startswith("Error")
    assert team.setting("tz") == tz
    assert call(1, "update_settings", tz="Europe/Lisbon", country="PT").startswith("Changed only")
    assert call(1, "update_settings", tz="Europe/Madrid").startswith("Changed only")  # a country is set: fine
    assert team.setting("country") == "PT"


def at(day, hour):
    return datetime.combine(day, datetime.min.time().replace(hour=hour), ZoneInfo("Europe/Moscow"))


@pytest.mark.parametrize("today, expected", [
    (date(2026, 11, 3), (date(2026, 11, 4), date(2026, 11, 5))),   # Tue before a Wednesday holiday
    (date(2027, 3, 5), (date(2027, 3, 8), date(2027, 3, 9))),      # Fri before a Monday holiday, across the weekend
    (date(2026, 12, 31), (date(2027, 1, 1), date(2027, 1, 11))),   # the long break, across a change of year
])
def test_a_holiday_ahead_is_found(today, expected):
    team.set_setting("country", "RU")
    first, name, back = team.holiday_ahead(today)
    assert (first, back) == expected and name


def test_the_last_working_day_before_a_holiday_gets_one_warning(setup, monkeypatch):
    team.set_setting("country", "RU")
    call(1, "set_status", status="vacation", day=date(2026, 11, 3))
    monkeypatch.setattr(team.Member, "now", lambda self: at(date(2026, 11, 3), 16))
    for _ in range(2):
        asyncio.run(scheduler.holiday_warning(team.member(1)))
        asyncio.run(scheduler.holiday_warning(team.member(2)))
    assert len(setup) == 1 and setup[0][0] == 2  # once, and not to the one on vacation
    assert "04.11" in setup[0][1] and "05.11" in setup[0][1]


@pytest.mark.parametrize("now", [
    at(date(2026, 11, 3), 15),  # too early
    at(date(2026, 11, 4), 16),  # the holiday itself
    at(date(2026, 11, 6), 16),  # Friday: an ordinary weekend follows
])
def test_no_holiday_warning_otherwise(setup, monkeypatch, now):
    team.set_setting("country", "RU")
    monkeypatch.setattr(team.Member, "now", lambda self: now)
    asyncio.run(scheduler.holiday_warning(team.member(2)))
    assert setup == []


def test_nothing_is_asked_or_summarised_on_a_holiday(setup, monkeypatch):
    team.set_setting("country", "RU")
    holiday = date(2026, 11, 4)
    monkeypatch.setattr(team.Member, "now", lambda self: at(holiday, 9))
    monkeypatch.setattr(team, "team_now", lambda: at(holiday, 13))
    db.run("INSERT INTO standups VALUES (2, ?, 'did X')", holiday.isoformat())
    asyncio.run(scheduler.tick())
    assert setup == []


def test_the_weekly_review_waits_out_a_monday_holiday(setup, monkeypatch):
    team.set_setting("country", "RU")
    days = []

    async def analysis(kind, start, end, member_id=None):
        days.append((start, end))
        return "review"

    monkeypatch.setattr(scheduler.reports, "analysis", analysis)
    monkeypatch.setattr(team, "team_now", lambda: at(date(2027, 3, 8), 13))  # Monday, Women's Day
    asyncio.run(scheduler.weekly())
    assert setup == []
    monkeypatch.setattr(team, "team_now", lambda: at(date(2027, 3, 9), 13))  # Tuesday: the same past week
    asyncio.run(scheduler.weekly())
    assert setup and set(days) == {(date(2027, 3, 1), date(2027, 3, 7))}
    setup.clear()
    monkeypatch.setattr(team, "team_now", lambda: at(date(2027, 3, 10), 13))  # Wednesday: already done
    asyncio.run(scheduler.weekly())
    assert setup == []


def test_only_a_button_removes_a_member(setup):
    assert call(1, "remove_member", member_id=2).startswith("NOT removed")
    assert team.member(2) and setup[-1][0] == 1  # the admin got the confirmation button
    tools.remove(2)
    assert team.member(2) is None


def test_members_request_absences_only_for_themselves():
    assert call(2, "request_absence", kind="sick", start=MONDAY, end=MONDAY, member_id=1).startswith("Error")
    assert "approved" in call(1, "request_absence", kind="sick", start=MONDAY, end=MONDAY, member_id=2)
    assert team.away(2, MONDAY) == "sick"


def test_schema_migrations_run_once_and_only_on_old_databases(tmp_path, monkeypatch):
    path = tmp_path / "bot.db"
    db.connect(path)  # created at the current schema: version 0, no steps
    db.run("INSERT INTO members (id, name) VALUES (7, 'Old')")
    monkeypatch.setattr(db, "MIGRATIONS", ["ALTER TABLE members ADD COLUMN nickname TEXT"])
    db.connect(path)  # the release with one new step
    db.connect(path)  # restarted: the step must not run again
    assert db.one("PRAGMA user_version")[0] == 1
    assert db.one("SELECT nickname FROM members WHERE id = 7")["nickname"] is None
    db.connect(tmp_path / "new.db")  # a new database starts at the latest version
    assert db.one("PRAGMA user_version")[0] == 1
    monkeypatch.setattr(db, "MIGRATIONS", [])
    with pytest.raises(SystemExit):
        db.connect(path)  # rolled back to older code
