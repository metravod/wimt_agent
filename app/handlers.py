"""Incoming Telegram updates: /start, text, voice and button presses. Private chats only."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from app import agent, bot, llm, team, tools
from app.texts import t

log = logging.getLogger(__name__)
router = Router()
router.message.filter(F.chat.type == "private")


@router.message(CommandStart())
async def start(message: Message, command: CommandObject) -> None:
    """The first person ever becomes the admin; everyone else joins with the invite link."""
    user = message.from_user
    if me := team.member(user.id):
        await message.answer(t("welcome", name=me.name))
    elif not team.members():
        team.set_setting("language", "ru" if user.language_code == "ru" else "en")
        team.add_member(user.id, user.full_name, user.username, is_admin=True)
        await message.answer(t("welcome_admin", name=user.first_name, link=bot.invite_link(team.invite_code()),
                               status_time=team.setting("status_time"), standup_time=team.setting("standup_time")))
    elif command.args == team.invite_code():
        for admin in team.admins():
            await bot.send(admin.id, t("joined", name=user.full_name))
        team.add_member(user.id, user.full_name, user.username)
        await message.answer(t("welcome", name=user.first_name))
    else:
        await message.answer(t("stranger"))


@router.message(F.text | F.voice)
async def talk(message: Message) -> None:
    me = team.member(message.from_user.id)
    if not me:
        await message.answer(t("stranger"))
        return
    typing = asyncio.create_task(keep_typing(message.chat.id))
    try:
        text = message.text
        if message.voice:
            audio = await bot.bot.download(message.voice)
            text = f"(voice message) {await llm.transcribe(audio.read())}"
        reply = await agent.answer(me, text)
    except Exception:
        log.exception("failed to answer %s", me.name)
        reply = t("error")
    finally:
        typing.cancel()
    await bot.send(me.id, reply)


async def keep_typing(chat_id: int) -> None:
    while True:
        await bot.bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(4)


@router.callback_query(F.data.startswith("status:"))
async def status_button(query: CallbackQuery) -> None:
    me = team.member(query.from_user.id)
    status = query.data.removeprefix("status:")
    if me and status in team.STATUSES:
        tools.set_status(me, status)
        await query.message.edit_text(t("status_set", status=t(status)))
    await query.answer()


@router.callback_query(F.data.startswith("absence:"))
async def absence_button(query: CallbackQuery) -> None:
    me = team.member(query.from_user.id)
    if not me or not me.is_admin:
        await query.answer()
        return
    _, absence_id, state = query.data.split(":")
    try:
        await tools.decide(int(absence_id), state)
        await query.message.edit_text(f"{query.message.text}\n\n{t(state)}")
        await query.answer()
    except tools.Refused as e:  # e.g. another admin already decided
        await query.answer(str(e), show_alert=True)


@router.callback_query(F.data.startswith("remove:"))
async def remove_button(query: CallbackQuery) -> None:
    """The only way to delete a member: the agent can ask, but a person has to press the button."""
    me = team.member(query.from_user.id)
    target = query.data.removeprefix("remove:")
    if me and me.is_admin and target != "cancel":
        try:
            await query.message.edit_text(t("removed", name=tools.remove(int(target))))
        except tools.Refused as e:  # already removed
            await query.message.edit_text(str(e))
    else:
        await query.message.edit_text(t("cancelled"))
    await query.answer()
