"""Runtime configuration.

The agent is provider-agnostic by design: it speaks to Groq, OpenAI or
Anthropic through one interface, and falls back to a fully deterministic
pipeline when no key is present. The demo can never be broken by a missing
key, a rate limit or an offline laptop.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "exec_agent.db"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Provider preference order: whichever key exists wins, Groq first.
PROVIDERS = {
    "groq": {
        "key": GROQ_API_KEY,
        "base_url": "https://api.groq.com/openai/v1",
        # Groq retires models regularly -- run `python check_llm.py` to list
        # what is currently available and switch with GROQ_MODEL in .env.
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "sdk": "openai",
    },
    "openai": {
        "key": OPENAI_API_KEY,
        "base_url": None,
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "sdk": "openai",
    },
    "anthropic": {
        "key": ANTHROPIC_API_KEY,
        "base_url": None,
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        "sdk": "anthropic",
    },
}


def active_provider() -> dict | None:
    for name, cfg in PROVIDERS.items():
        if cfg["key"]:
            return {"name": name, **cfg}
    return None


def llm_enabled() -> bool:
    return active_provider() is not None


def mode() -> str:
    p = active_provider()
    return f"llm:{p['name']}" if p else "deterministic"


# The data pack is a fixed, self-contained week. "Today" for the agent is a
# parameter, not the wall clock -- this is what lets a reviewer replay the week
# day by day and watch deadlines slip in real time.
WEEK_START = "2026-09-21"
WEEK_END = "2026-09-25"
DEFAULT_AS_OF = "2026-09-23T09:00"
