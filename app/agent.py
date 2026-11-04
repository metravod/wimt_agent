"""The agent: a message comes in, the model calls tools as it sees fit, a reply goes out."""
import asyncio
import logging

from app import bot, db, llm, team, tools
from app.team import Member
from app.texts import t

log = logging.getLogger(__name__)

MAX_STEPS = 8   # rounds of tool calls per message
MEMORY = 20     # past messages the agent sees

# One turn at a time per member: Telegram updates are handled concurrently, and a second message sent
# while the first is still being answered must see that answer, not race it (and repeat its tools).
turns: dict[int, asyncio.Lock] = {}


async def answer(me: Member, text: str) -> str:
    async with turns.setdefault(me.id, asyncio.Lock()):
        return await take_turn(me, text)


async def take_turn(me: Member, text: str) -> str:
    history = db.q("SELECT role, content FROM chat WHERE member_id = ? ORDER BY id DESC LIMIT ?", me.id, MEMORY)
    messages = [{"role": "system", "content": context(me)},
                *[dict(row) for row in reversed(history)],
                {"role": "user", "content": text}]
    reply, done = None, []  # done: what the tools changed or sent during this turn
    try:
        for _ in range(MAX_STEPS):
            message = await llm.chat(messages, tools.schemas(me))
            if not message.tool_calls:
                reply = message.content
                break
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                result = await tools.call(me, call.function.name, call.function.arguments)
                log.info("%s: %s %s -> %s", me.name, call.function.name, call.function.arguments, result[:100])
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
                if not result.startswith("Error") and not tools.TOOLS[call.function.name].reads:
                    done.append(result)
    except Exception:
        if not done:
            raise  # nothing happened yet: the handler apologises, and there is nothing to remember
        log.exception("%s: the turn broke off after its tools acted", me.name)
    if not reply:
        # Say what was already done, and remember it, so that "try again" does not do it twice
        # (a second absence request to the admins, a second announcement).
        reply = t("error_done") + "".join(f"\n• {result}" for result in done) if done else t("error")
    remember(me, text, reply)
    return reply


def remember(me: Member, text: str, reply: str) -> None:
    db.run("INSERT INTO chat (member_id, role, content) VALUES (?, 'user', ?), (?, 'assistant', ?)",
           me.id, text, me.id, reply)
    db.run("DELETE FROM chat WHERE member_id = ? AND id NOT IN "
           "(SELECT id FROM chat WHERE member_id = ? ORDER BY id DESC LIMIT ?)", me.id, me.id, MEMORY)


def context(me: Member) -> str:
    """The system prompt: the rules from prompts/agent.md plus a fresh snapshot of the team."""
    now = me.now()
    today = now.date()
    roster = []
    for m in team.members():
        line = f"- {m.id}: {m.name}" + (f" (@{m.username})" if m.username else "") + (" [admin]" if m.is_admin else "")
        line += f" — today {team.status(m.id, today) or 'no status'}, standup {'sent' if team.standup(m.id, today) else 'not sent'}"
        roster.append(line + (" ← you are talking to this person" if m.id == me.id else ""))
    admin = []
    if me.is_admin:
        pending = db.q("SELECT a.*, m.name FROM absences a JOIN members m ON m.id = a.member_id "
                       "WHERE a.state = 'pending' ORDER BY a.id")
        admin = [
            f"They are an admin. Invite link for new members: {bot.invite_link(team.invite_code())}",
            "Team settings: " + ", ".join(f"{k}={team.setting(k)}" for k in team.DEFAULTS),
            "Absence requests waiting for a decision: " + ("; ".join(
                f"#{r['id']} {r['name']}, {r['kind']} {r['start_day']} – {r['end_day']}" for r in pending) or "none"),
        ]
        if not db.one("SELECT 1 FROM settings WHERE key = 'tz'"):
            admin.append("The team time zone was never set: ask where the team is based, then set tz and country.")
    return llm.prompt("agent").format(
        now=now.strftime("%A %Y-%m-%d %H:%M"), tz=now.tzname(), day=team.day_off(today) or "a workday",
        name=me.name, roster="\n".join(roster), admin="\n".join(admin),
    )
