"""Reports the model writes from the team's standups: daily summary, retro, weekly review."""
from datetime import date

from app import db, llm, team


def standups(start: date, end: date, member_id: int | None = None) -> str:
    rows = db.q("SELECT s.day, m.name, s.text FROM standups s JOIN members m ON m.id = s.member_id "
                "WHERE s.day BETWEEN ? AND ? AND (? IS NULL OR s.member_id = ?) ORDER BY s.day, m.name",
                start.isoformat(), end.isoformat(), member_id, member_id)
    return "\n\n".join(f"{r['day']} — {r['name']}:\n{r['text']}" for r in rows)


async def daily_summary(day: date) -> str:
    reports, absent, silent = [], [], []
    for m in team.members():
        if kind := team.away(m.id, day):
            absent.append(f"{m.name} ({kind})")
        elif text := team.standup(m.id, day):
            reports.append(f"{m.name}:\n{text}")
        else:
            silent.append(m.name)
    return await llm.write("summary", "\n\n".join(reports)
                           + f"\n\nAbsent: {', '.join(absent) or 'nobody'}"
                           + f"\nDid not report: {', '.join(silent) or 'nobody'}")


async def analysis(prompt_name: str, start: date, end: date, member_id: int | None = None) -> str | None:
    """Retro / weekly review over a period; None when there are no standups to analyse."""
    material = standups(start, end, member_id)
    if not material:
        return None
    return await llm.write(prompt_name, f"Standups from {start} to {end}:\n\n{material}")
