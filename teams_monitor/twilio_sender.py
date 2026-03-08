"""
Envia mensagens WhatsApp via Twilio API (sandbox ou produção).
"""
import requests
from rich.console import Console

from .config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM,
    TWILIO_TO,
)

console = Console()

_TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def send_twilio(message: str, to: str | None = None) -> bool:
    """
    Envia uma mensagem via Twilio (WhatsApp ou SMS).

    Args:
        message: Texto da mensagem.
        to:      Número destino. Usa TWILIO_TO do .env se omitido.

    Returns:
        True se enviado com sucesso, False caso contrário.
    """
    target = to or TWILIO_TO

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        console.print("[red]❌ TWILIO_ACCOUNT_SID ou TWILIO_AUTH_TOKEN não configurados no .env[/red]")
        return False
    if not TWILIO_FROM or not target:
        console.print("[red]❌ TWILIO_FROM ou TWILIO_TO não configurados no .env[/red]")
        return False

    url = _TWILIO_API.format(sid=TWILIO_ACCOUNT_SID)
    try:
        resp = requests.post(
            url,
            data={"From": TWILIO_FROM, "To": target, "Body": message},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            console.print(f"[green]📨 Twilio enviado para {target} (SID: {data.get('sid', '?')})[/green]")
            return True
        else:
            console.print(f"[red]❌ Twilio erro {resp.status_code}: {data.get('message', resp.text)}[/red]")
            return False
    except requests.exceptions.ConnectionError:
        console.print("[red]❌ Sem conexão com internet para enviar via Twilio.[/red]")
        return False
    except Exception as exc:
        console.print(f"[red]❌ Erro ao enviar Twilio: {exc}[/red]")
        return False


def check_twilio_status() -> bool:
    """Verifica se as credenciais Twilio estão configuradas e válidas."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}.json"
    try:
        resp = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=5)
        return resp.status_code == 200
    except Exception:
        return False
