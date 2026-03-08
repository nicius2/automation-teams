"""
Agendador de tarefas: executa check_mentions() em intervalos regulares,
apenas em dias úteis e dentro do horário configurado.

Melhorias:
  - Deduplicação por hash do conteúdo (não por id que nunca existe)
  - Persiste IDs notificados em disco (notified.json) entre reinicializações
"""
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from rich.console import Console

from .config import (
    CHECK_INTERVAL_MINUTES,
    MONITOR_START_TIME,
    MONITOR_END_TIME,
)
from .teams_client import check_mentions
from .telegram_sender import send_telegram, check_telegram_status

console = Console()

# Arquivo para persistir hashes de mensagens notificadas
_NOTIFIED_FILE = Path(__file__).parent.parent / "notified.json"
_MAX_NOTIFIED = 500  # evita crescimento infinito


def _load_notified() -> set[str]:
    """Carrega hashes de mensagens já notificadas do disco."""
    try:
        if _NOTIFIED_FILE.exists():
            data = json.loads(_NOTIFIED_FILE.read_text())
            return set(data)
    except Exception:
        pass
    return set()


def _save_notified(notified: set[str]) -> None:
    """Persiste os hashes no disco (mantém no máximo _MAX_NOTIFIED)."""
    try:
        items = list(notified)
        if len(items) > _MAX_NOTIFIED:
            items = items[-_MAX_NOTIFIED:]  # mantém os mais recentes
        _NOTIFIED_FILE.write_text(json.dumps(items))
    except Exception:
        pass


def _message_hash(item: dict) -> str:
    """Gera um hash único para uma mensagem baseado no conteúdo."""
    content = item.get("message", {}).get("body", {}).get("content", "")
    channel = item.get("channel", "")
    # Hash curto (16 chars) do conteúdo + canal
    raw = f"{channel}::{content}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _is_work_hours() -> bool:
    """Verifica se estamos dentro do horário configurado."""
    now = datetime.now()

    start_h, start_m = map(int, MONITOR_START_TIME.split(":"))
    end_h, end_m = map(int, MONITOR_END_TIME.split(":"))

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    current_minutes = now.hour * 60 + now.minute

    return start_minutes <= current_minutes <= end_minutes


def run_check() -> None:
    """
    Tarefa principal executada pelo scheduler.
    Verifica menções e envia notificações WhatsApp para as novas.
    """
    if not _is_work_hours():
        console.print(
            f"[dim]{datetime.now().strftime('%H:%M')} — Fora do horário "
            f"({MONITOR_START_TIME}–{MONITOR_END_TIME}). Aguardando...[/dim]"
        )
        return

    console.print(f"\n[bold cyan]⏰ {datetime.now().strftime('%d/%m %H:%M')} — Verificando menções...[/bold cyan]")

    # Verifica se Telegram está acessível
    if not check_telegram_status():
        console.print("[yellow]⚠️  Telegram não acessível. Verifique TELEGRAM_BOT_TOKEN no .env.[/yellow]")
        return

    mentions = check_mentions()
    if not mentions:
        return

    # Carrega hashes já notificados
    notified = _load_notified()
    new_count = 0

    for item in mentions:
        msg_hash = _message_hash(item)
        if msg_hash in notified:
            continue  # já notificamos essa mensagem

        sent = send_telegram(item["formatted_text"])
        if sent:
            notified.add(msg_hash)
            new_count += 1

    if new_count:
        _save_notified(notified)
        console.print(f"[green]✅ {new_count} nova(s) notificação(ões) enviadas.[/green]")
    else:
        console.print("[dim]  Todas as menções já foram notificadas anteriormente.[/dim]")


def start_scheduler() -> None:
    """Inicia o scheduler bloqueante."""
    console.print(
        f"\n[bold]📅 Scheduler iniciado[/bold]\n"
        f"  ⏱  Intervalo: a cada {CHECK_INTERVAL_MINUTES} minuto(s)\n"
        f"  🕐 Horário:   {MONITOR_START_TIME} – {MONITOR_END_TIME} (dias úteis)\n"
    )

    console.print("[bold yellow]🚀 Executando verificação inicial...[/bold yellow]")
    run_check()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINUTES),
        id="check_mentions",
        name="Verificar menções no Teams",
        misfire_grace_time=60,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]⏹  Scheduler encerrado.[/yellow]")
