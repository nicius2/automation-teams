"""
Envia mensagens WhatsApp via servidor Baileys local (HTTP).
"""
import requests
from rich.console import Console

from .config import BAILEYS_SERVER_URL, WHATSAPP_TARGET_PHONE

console = Console()


def send_whatsapp(message: str, phone: str | None = None) -> bool:
    """
    Envia uma mensagem via Baileys REST API.

    Args:
        message: Texto da mensagem a enviar.
        phone:   Número destino. Usa WHATSAPP_TARGET_PHONE se omitido.

    Returns:
        True se enviou com sucesso, False caso contrário.
    """
    target = phone or WHATSAPP_TARGET_PHONE
    if not target:
        console.print("[red]❌ WHATSAPP_TARGET_PHONE não configurado no .env[/red]")
        return False

    try:
        resp = requests.post(
            f"{BAILEYS_SERVER_URL}/send-message",
            json={"phone": target, "message": message},
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("success"):
            console.print(f"[green]📤 WhatsApp enviado para {target}[/green]")
            return True
        else:
            console.print(f"[red]❌ Baileys retornou erro: {resp.text}[/red]")
            return False
    except requests.exceptions.ConnectionError:
        console.print(
            "[red]❌ Servidor Baileys não está rodando em "
            f"{BAILEYS_SERVER_URL}. Inicie com: cd whatsapp-server && npm start[/red]"
        )
        return False
    except Exception as exc:
        console.print(f"[red]❌ Erro ao enviar WhatsApp: {exc}[/red]")
        return False


def check_baileys_status() -> bool:
    """Verifica se o servidor Baileys está ativo e conectado ao WhatsApp."""
    try:
        resp = requests.get(f"{BAILEYS_SERVER_URL}/status", timeout=5)
        data = resp.json()
        return data.get("ready", False)
    except Exception:
        return False
