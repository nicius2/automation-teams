"""
Configurações centrais carregadas do arquivo .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega o .env na raiz do projeto
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")

# ── Browser / Playwright ───────────────────────────────────────────────────────
BROWSER_SESSION_DIR: Path = _root / "browser_session"
BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"

# ── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Monitor ────────────────────────────────────────────────────────────────────
MENTION_TARGETS: list[str] = [
    t.strip().lower()
    for t in os.getenv("MENTION_TARGETS", "jose").split(",")
    if t.strip()
]

MONITOR_START_TIME: str = os.getenv("MONITOR_START_TIME", "08:00")
MONITOR_END_TIME: str = os.getenv("MONITOR_END_TIME", "18:00")
CHECK_INTERVAL_MINUTES: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))
