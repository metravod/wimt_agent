"""The language model: chat with tools, one-shot writing from a prompt, voice transcription."""
from pathlib import Path

from openai import AsyncOpenAI

from app import config, team
from app.texts import LANGUAGES

client = AsyncOpenAI(api_key=config.OPENAI_API_KEY or "missing")
PROMPTS = Path(__file__).parent / "prompts"


def prompt(name: str) -> str:
    """A prompt from app/prompts/, or your own copy from DATA_DIR/prompts/ if you placed one there."""
    custom = config.DATA_DIR / "prompts" / f"{name}.md"
    return (custom if custom.exists() else PROMPTS / f"{name}.md").read_text()


async def chat(messages: list[dict], tools: list[dict]):
    response = await client.chat.completions.create(model=config.MODEL, messages=messages, tools=tools)
    return response.choices[0].message


async def write(prompt_name: str, material: str) -> str:
    """Produce a report from a prompt and raw material, in the team's language."""
    language = LANGUAGES.get(team.setting("language"), "English")
    system = f"{prompt(prompt_name)}\n\nWrite in {language}. Plain text: no Markdown or HTML, emoji are fine."
    response = await client.chat.completions.create(model=config.MODEL, messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": material},
    ])
    return response.choices[0].message.content or ""


async def transcribe(audio: bytes) -> str:
    result = await client.audio.transcriptions.create(model=config.TRANSCRIBE_MODEL, file=("voice.ogg", audio))
    return result.text
