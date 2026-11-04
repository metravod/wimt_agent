"""Run the agent on evals/cases.py against the real model.

    OPENAI_API_KEY=... python -m evals [--runs 3] [--model gpt-5.4-mini] [name filter]

Every case runs several times on a fresh in-memory team, because the model is not deterministic:
a case that passes 2 runs of 3 is a real problem, just a rarer one. Costs a few cents.
Not part of CI (needs a key); run it after changing prompts, tools or the model.
"""
import argparse
import asyncio
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import agent, bot, config, db, team, tools
from evals.cases import CASES, TODAY

NOW = datetime(2026, 9, 30, 10, 0, tzinfo=ZoneInfo("Europe/Moscow"))
PEOPLE = {"Anna": (1, "Анна Смирнова", True), "Boris": (2, "Борис Петров", False), "Vika": (3, "Вика Орлова", False)}
TABLES = ("members", "statuses", "standups", "absences", "notes", "settings", "team_days_off")
NAMESAKE = 4


class World:
    """The team before a case, plus helpers for the checks."""

    def __init__(self):
        db.connect(":memory:")
        for key, (member_id, name, admin) in PEOPLE.items():
            team.add_member(member_id, name, key.lower(), admin)
        for key, value in {"language": "ru", "tz": "Europe/Moscow", "country": "RU"}.items():
            team.set_setting(key, value)
        team.invite_code()
        db.run("INSERT INTO statuses VALUES (3, ?, 'office')", TODAY.isoformat())
        db.run("INSERT INTO standups VALUES (3, ?, ?)", TODAY.isoformat(),
               "Вчера мигрировала базу на Postgres 17, сегодня чищу старые таблицы. Блокеров нет.")
        self.sent, self.calls, self.reply, self.before = [], [], "", None

    def id(self, who):
        return PEOPLE[who][0]

    def member(self, who):
        return team.member(self.id(who))

    def status(self, who, day=TODAY):
        return team.status(self.id(who), day)

    def standup(self, who, day=TODAY):
        return team.standup(self.id(who), day)

    def notes(self, who):
        return db.q("SELECT * FROM notes WHERE member_id = ?", self.id(who))

    def setting(self, key):
        return team.setting(key)

    def configure(self, **settings):
        for key, value in settings.items():
            team.set_setting(key, value)

    def messaged(self, who):
        return any(chat == self.id(who) for chat, _ in self.sent)

    def absence(self, who, kind, start, end=None, state=None):
        rows = db.q("SELECT * FROM absences WHERE member_id = ? AND kind = ? AND start_day = ?", self.id(who), kind, start)
        return any((end is None or r["end_day"] == end) and (state is None or r["state"] == state) for r in rows)

    def request(self, who, kind, start, end):
        db.run("INSERT INTO absences (member_id, kind, start_day, end_day) VALUES (?, ?, ?, ?)",
               self.id(who), kind, start, end)

    def standups_last_week(self):
        work = {"Boris": ["логин", "логин", "ревью", "экспорт csv", "экспорт csv"],
                "Vika": ["миграция базы", "миграция базы", "миграция базы", "блокер: нет доступа к стейджу", "чистка таблиц"]}
        for who, topics in work.items():
            for offset, topic in enumerate(topics):
                day = TODAY - timedelta(days=9 - offset)  # Mon 21 … Fri 25 Sep
                db.run("INSERT INTO standups VALUES (?, ?, ?)", self.id(who), day.isoformat(), f"Работаю над: {topic}")

    def dump(self):
        return [[tuple(r) for r in db.q(f"SELECT * FROM {table} ORDER BY 1, 2")] for table in TABLES]

    def day_off(self, day=TODAY):
        return team.day_off(day)

    def add_namesake(self):
        """A second Анна on the team, and the first one marked as in the office today."""
        team.add_member(NAMESAKE, "Анна Ким", "annakim", False)
        db.run("INSERT INTO statuses VALUES (?, ?, 'office')", self.id("Anna"), TODAY.isoformat())

    def namesake_untouched(self):
        return team.status(NAMESAKE, TODAY) is None and not self.sent

    def statuses_untouched(self):
        return self.dump()[TABLES.index("statuses")] == self.before[TABLES.index("statuses")]

    def untouched(self):
        return self.dump() == self.before


world: World


def record(call):
    async def recorded(me, name, arguments):
        result = await call(me, name, arguments)
        world.calls.append(f"{name}({arguments}) → {result[:90]}")
        return result
    return recorded


async def send(chat_id, text, markup=None):
    world.sent.append((chat_id, text))


async def run(case) -> bool:
    global world
    world = World()
    if case.setup:
        case.setup(world)
    world.before = world.dump()
    world.reply = await agent.answer(world.member(case.who), case.message)
    return bool(case.check(world)) and not (case.forbid and re.search(case.forbid, world.reply))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filter", nargs="?", default="", help="run only cases whose name contains this")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default=config.MODEL)
    args = parser.parse_args()

    config.MODEL = args.model
    bot.send, bot.username = send, "team_bot"
    tools.call = record(tools.call)
    team.Member.now = lambda self: NOW.astimezone(ZoneInfo(self.tz or team.setting("tz")))
    team.team_now = lambda: NOW.astimezone(ZoneInfo(team.setting("tz")))

    cases = [c for c in CASES if args.filter in c.name]
    print(f"{config.MODEL}, {len(cases)} cases × {args.runs} runs\n")
    perfect = 0
    for case in cases:
        failures = []
        for _ in range(args.runs):
            if not await run(case):
                failures.append((world.reply, world.calls))
        passed = args.runs - len(failures)
        known = bool(failures) and "known" in case.tags
        perfect += not failures or known
        print(f"{'✓' if not failures else '~' if known else '✗'} {passed}/{args.runs}  {case.name}")
        for reply, calls in failures[:1]:
            print(f"      {case.who}: {case.message}")
            for line in calls or ["(no tool calls)"]:
                print(f"      · {line}")
            print(f"      → {reply[:300]}")
    print(f"\n{perfect}/{len(cases)} cases passed every run")
    return 0 if perfect == len(cases) else 1


sys.exit(asyncio.run(main()))
