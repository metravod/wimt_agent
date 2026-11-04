"""Every knob the bot reads from the environment. Only the first two are required.

The OpenAI client additionally picks up OPENAI_BASE_URL by itself, which lets you
point the bot at any OpenAI-compatible provider (OpenRouter, a local Ollama, ...).
"""
import os
from pathlib import Path

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

MODEL = os.getenv("MODEL", "gpt-5.4-nano")
TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "whisper-1")
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
