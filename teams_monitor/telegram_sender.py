"""
Envia mensagens via Telegram Bot API.
Muito mais simples que WhatsApp — sem servidor Node.js, sem sessão corrompida.
"""
import requests
from rich.console import Console

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

console = Console()

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def send_telegram(message: str, chat_id: str | None = None) -> bool:
    """
    Envia uma mensagem via Telegram Bot API.

    Args:
        message:  Texto da mensagem (suporta Markdown do Telegram).
        chat_id:  ID do chat/usuário destino. Usa TELEGRAM_CHAT_ID se omitido.

    Returns:
        True se enviou com sucesso, False caso contrário.
    """
    target = chat_id or TELEGRAM_CHAT_ID
    if not target:
        console.print("[red]❌ TELEGRAM_CHAT_ID não configurado no .env[/red]")
        console.print("[dim]  Execute: python main.py --get-chat-id[/dim]")
        return False

    if not TELEGRAM_BOT_TOKEN:
        console.print("[red]❌ TELEGRAM_BOT_TOKEN não configurado no .env[/red]")
        return False

    url = _TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN, method="sendMessage")
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": target,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            console.print(f"[green]📨 Telegram enviado para chat {target}[/green]")
            return True
        else:
            console.print(f"[red]❌ Telegram erro: {data.get('description', resp.text)}[/red]")
            return False
    except requests.exceptions.ConnectionError:
        console.print("[red]❌ Sem conexão com internet para enviar via Telegram.[/red]")
        return False
    except Exception as exc:
        console.print(f"[red]❌ Erro ao enviar Telegram: {exc}[/red]")
        return False


def get_my_chat_id() -> str | None:
    """
    Lê as atualizações recentes do bot para descobrir o chat_id do usuário.
    O usuário precisa ter enviado uma mensagem para o bot antes.
    """
    if not TELEGRAM_BOT_TOKEN:
        return None

    url = _TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN, method="getUpdates")
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("ok") and data.get("result"):
            # Pega o chat_id da última mensagem recebida
            last = data["result"][-1]
            msg = last.get("message") or last.get("channel_post") or {}
            chat = msg.get("chat", {})
            return str(chat.get("id", ""))
    except Exception:
        pass
    return None


def check_telegram_status() -> bool:
    """Verifica se o bot está configurado e acessível."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = _TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN, method="getMe")
    try:
        resp = requests.get(url, timeout=5)
        return resp.json().get("ok", False)
    except Exception:
        return False
