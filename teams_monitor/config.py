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
TELEGRAM_REQUEST_TIMEOUT: int = int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "20"))

# ── Monitor ────────────────────────────────────────────────────────────────────
MENTION_TARGETS: list[str] = [
    t.strip().lower()
    for t in os.getenv("MENTION_TARGETS", "jose").split(",")
    if t.strip()
]

MONITOR_START_TIME: str = os.getenv("MONITOR_START_TIME", "08:00")
MONITOR_END_TIME: str = os.getenv("MONITOR_END_TIME", "18:00")

# Intervalo de verificação - suporta minutos ou segundos
# Opção 1: CHECK_INTERVAL_MINUTES (padrão) - em minutos
# Opção 2: CHECK_INTERVAL_SECONDS - em segundos (sobrescreve a opção 1)
_check_seconds = os.getenv("CHECK_INTERVAL_SECONDS", "")
if _check_seconds:
    CHECK_INTERVAL_SECONDS: int = int(_check_seconds)
else:
    _check_minutes = os.getenv("CHECK_INTERVAL_MINUTES", "5")
    CHECK_INTERVAL_SECONDS: int = int(float(_check_minutes) * 60)

CHECK_INTERVAL_MINUTES: int = CHECK_INTERVAL_SECONDS // 60


