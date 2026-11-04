# wimt_agent

[![omut](https://github.com/metravod/wimt_agent/actions/workflows/omut.yml/badge.svg?branch=main)](.omut/)

*wimt: where is my team.*

A Telegram assistant for a small team. Nobody has to learn commands: people just write to it.

> **Me:** remote today. Yesterday fixed the login bug, today code review, no blockers
> **Bot:** Done: you're remote today and your standup is saved.
>
> **Me:** I'd like a vacation Oct 12–16
> **Bot:** Request sent to the admins. *(the admin gets it with Approve / Reject buttons)*
>
> **Admin:** who's in the office today and who hasn't sent a standup?

It also keeps the daily rhythm on its own: every morning it asks where everyone is working and asks for the standup, reminds the people who forgot, and sends a summary of all standups once everyone has reported. On the first working day of the week it sends a review of the past week. It skips weekends, public holidays, days an admin declares off and people on vacation, and warns the team on the last working day before a day off. You can send it voice messages, too.

It talks in whatever language you write to it.

## Set it up in 10 minutes

You need three things. None of them requires programming.

**1. A Telegram bot.** In Telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, choose a name. It replies with a **token** like `123456:ABC-DEF...`. Copy it.

**2. An OpenAI key.** Sign in at [platform.openai.com](https://platform.openai.com/api-keys), add a few dollars of credit, click *Create new secret key*, and copy the **key** (`sk-...`). For a small team with the default model it costs cents to a couple of dollars a month.

**3. A computer that is always on.** The cheapest cloud server from any provider (Hetzner, DigitalOcean, ...) with Ubuntu is plenty. The provider shows you how to open its console, or you connect with `ssh root@<server address>` from your computer's terminal.

In that console, paste this line and press Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/metravod/wimt_agent/main/install.sh | sh
```

It installs everything and asks for the token and the key. When it says *Done*, open your bot in Telegram and send `/start`. **The first person to do this becomes the admin.** The bot gives the admin an invite link to share with the team, and asks where the team is based, so it knows the time zone and holidays.

That's it. Everything else — times, time zone, who is an admin — you change by telling the bot, e.g. *"ask for standups at 10:30"*.

**Updating:** run the same line again. Your data is kept.

## Your data

Everything the bot knows lives in one file on your server (a Docker volume named `wimt-agent`). Nothing is sent anywhere except:

- **Telegram**, which delivers the messages;
- **OpenAI** (or the provider you choose), which receives the messages people write to the bot, plus the standups, when it writes summaries and answers. OpenAI does not train on API data by default.

A removed member's data is deleted with them. To back up, copy the volume:
`docker run --rm -v wimt-agent:/data -v "$PWD":/backup alpine cp /data/bot.db /backup/`

## Settings

Only the first two are required. Put the others in `~/.wimt-agent.env` next to them and re-run the installer.

| Variable | Default | What it does |
|---|---|---|
| `BOT_TOKEN` | — | Telegram bot token |
| `OPENAI_API_KEY` | — | Model provider key |
| `OPENAI_BASE_URL` | OpenAI | Any OpenAI-compatible provider, e.g. `https://openrouter.ai/api/v1` |
| `MODEL` | `gpt-5.4-nano` | Model for the agent and reports |
| `TRANSCRIBE_MODEL` | `whisper-1` | Model for voice messages |

**Your own prompts:** copy any file from [`app/prompts/`](app/prompts) into `/data/prompts/` inside the volume and edit it; the bot uses your copy instead. Keep the `{placeholders}` in `agent.md`.

## How it works (for reviewers)

About a thousand lines of Python, one job per file:

| File | What it does |
|---|---|
| [`app/tools.py`](app/tools.py) | **Everything the agent can do.** Each tool is a plain function; read this file to know what the AI can and cannot touch |
| [`app/agent.py`](app/agent.py) | The loop: message → model → tool calls → reply |
| [`app/prompts/`](app/prompts) | The agent's instructions and the report prompts |
| [`app/scheduler.py`](app/scheduler.py) | The daily rhythm: pings, reminders, summaries. A plain clock, no AI decisions |
| [`app/handlers.py`](app/handlers.py) | Incoming Telegram messages, voice and buttons |
| [`app/team.py`](app/team.py) | Members, settings, calendar |
| [`app/db.py`](app/db.py) | The whole database schema (SQLite) |
| [`app/reports.py`](app/reports.py) | Summary, retro and weekly review |
| [`app/bot.py`](app/bot.py), [`app/llm.py`](app/llm.py), [`app/texts.py`](app/texts.py) | Sending messages, calling the model, fixed texts |

Safety model: the agent never decides *who* is talking. Every tool gets the sender from Telegram, so a member can only act as themselves; admin tools are not even shown to other members. Only people with the invite link can join. There is no free-form database access.

Run locally: `pip install -r requirements.txt`, then `BOT_TOKEN=... OPENAI_API_KEY=... python -m app`. Tests: `pip install pytest && python -m pytest`.

What an admin does to other people doesn't depend on the model's judgement: removing a member and changing someone else's status or absence only happen when the admin presses a confirmation button.

**Evals.** The model is not deterministic, so [`evals/cases.py`](evals/cases.py) lists what the agent must get right — everyday messages, questions, and attempts to do what one isn't allowed to — and checks the outcome in the database. Run them after changing prompts, tools or the model (costs a few cents): `OPENAI_API_KEY=... python -m evals`. When the agent gets something wrong in real life, add a case first, then fix it.

**Changing the database.** The schema lives in [`app/db.py`](app/db.py); existing databases are upgraded by the `MIGRATIONS` list in the same file.

## License

MIT
