"""Outgoing Telegram messages. Incoming ones are in handlers.py."""
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

log = logging.getLogger(__name__)

bot: Bot
username = ""  # the bot's @username, for invite links


async def start(token: str) -> Bot:
    global bot, username
    bot = Bot(token)
    username = (await bot.me()).username
    return bot


def invite_link(code: str) -> str:
    return f"https://t.me/{username}?start={code}"


def buttons(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """buttons([("Yes", "cb:yes"), ("No", "cb:no")]) -> an inline keyboard, one list per row."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows
    ])


async def send(chat_id: int, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Send a message, splitting long ones; a member who blocked the bot is logged, not fatal."""
    try:
        for i in range(0, len(text), 4000):
            await bot.send_message(chat_id, text[i:i + 4000], reply_markup=markup if i + 4000 >= len(text) else None)
    except Exception as e:
        log.warning("could not message %s: %s", chat_id, e)
