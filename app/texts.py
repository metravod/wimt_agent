"""The few fixed messages the bot sends on its own. Everything else is written by the agent.

To add a language, add one more block with the same keys.
"""
from app import team

TEXTS = {
    "en": {
        "office": "🏢 Office", "remote": "🏠 Remote", "day_off": "☀️ Day off",
        "vacation": "🏝 Vacation", "sick": "🤒 Sick", "travel": "🚆 Travelling",
        "welcome_admin": ("Hi {name}! You are the admin of this team bot.\n\n"
                          "Invite your teammates with this link:\n{link}\n\n"
                          "Tell me your city (for the time zone and public holidays) and, if you like, "
                          "when to ask for statuses and standups. Defaults: {status_time} and {standup_time}."),
        "welcome": ("Hi {name}! You're in the team.\n\nJust write to me like to a person: "
                    "where you are today, your standup, a vacation request, or a question about the team."),
        "joined": "👋 {name} joined the team.",
        "stranger": "This is a private team bot. Ask the team admin for an invite link.",
        "status_ask": "Good morning! Where are you working today?",
        "status_remind": "Reminder: you haven't set today's status yet.",
        "status_set": "Today: {status}",
        "standup_ask": "Time for the standup: what did you do yesterday, what's the plan for today, any blockers?",
        "standup_remind": "Reminder: the standup summary goes out at {time}, and yours is still missing.",
        "holiday_warning": "🎉 A holiday is coming: {name} ({day}). No status or standup questions until {back}. Enjoy!",
        "summary": "📋 Standup summary, {day}\n\n{text}",
        "weekly_team": "📅 Team week in review\n\n{text}",
        "weekly_personal": "📅 Your week in review\n\n{text}",
        "absence_ask": "{name} requests {kind}: {start} – {end}{reason}",
        "absence_decided": "Your {kind} request for {start} – {end} was {state}.",
        "approved": "approved ✅", "rejected": "rejected ❌",
        "approve": "✅ Approve", "reject": "❌ Reject",
        "remove_ask": "Remove {name} from the team, with all their data?",
        "remove": "🗑 Remove", "cancel": "Cancel",
        "removed": "{name} was removed from the team.", "cancelled": "Cancelled.",
        "error": "Something went wrong on my side, please try again in a minute.",
        "error_done": "Something went wrong on my side halfway through. This much is already done:",
    },
    "ru": {
        "office": "🏢 В офисе", "remote": "🏠 Удалёнка", "day_off": "☀️ Отгул",
        "vacation": "🏝 Отпуск", "sick": "🤒 Больничный", "travel": "🚆 В дороге",
        "welcome_admin": ("Привет, {name}! Ты админ этого командного бота.\n\n"
                          "Зови коллег по этой ссылке:\n{link}\n\n"
                          "Напиши, в каком ты городе (для часового пояса и праздников) и, если хочешь, "
                          "во сколько спрашивать статусы и дейли. По умолчанию: {status_time} и {standup_time}."),
        "welcome": ("Привет, {name}! Ты в команде.\n\nПросто пиши мне как человеку: "
                    "где ты сегодня, свой дейли, заявку на отпуск или вопрос про команду."),
        "joined": "👋 {name} присоединился к команде.",
        "stranger": "Это закрытый бот команды. Попроси у админа ссылку-приглашение.",
        "status_ask": "Доброе утро! Где сегодня работаешь?",
        "status_remind": "Напоминаю: статус на сегодня ещё не отмечен.",
        "status_set": "Сегодня: {status}",
        "standup_ask": "Время дейли: что делал вчера, что планируешь сегодня, есть ли блокеры?",
        "standup_remind": "Напоминаю: саммари дейли уйдёт в {time}, а твоего ещё нет.",
        "holiday_warning": "🎉 Впереди праздник: {name} ({day}). Статусы и дейли не спрашиваю до {back}. Хорошего отдыха!",
        "summary": "📋 Саммари дейли, {day}\n\n{text}",
        "weekly_team": "📅 Неделя команды\n\n{text}",
        "weekly_personal": "📅 Твоя неделя\n\n{text}",
        "absence_ask": "{name} просит {kind}: {start} – {end}{reason}",
        "absence_decided": "Заявка на {kind} {start} – {end}: {state}.",
        "approved": "одобрена ✅", "rejected": "отклонена ❌",
        "approve": "✅ Одобрить", "reject": "❌ Отклонить",
        "remove_ask": "Удалить {name} из команды вместе со всеми данными?",
        "remove": "🗑 Удалить", "cancel": "Отмена",
        "removed": "{name} больше не в команде.", "cancelled": "Отменено.",
        "error": "У меня что-то сломалось, попробуй через минуту.",
        "error_done": "У меня что-то сломалось на полпути. Вот что уже сделано:",
    },
}

LANGUAGES = {"en": "English", "ru": "Russian"}


def t(key: str, **kwargs) -> str:
    lang = team.setting("language")
    return TEXTS.get(lang, TEXTS["en"])[key].format(**kwargs)
