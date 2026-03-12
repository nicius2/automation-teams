"""
Agendador de tarefas: executa check_mentions() em intervalos regulares,
apenas em dias úteis e dentro do horário configurado.

Melhorias:
  - Deduplicação por hash do conteúdo (não por id que nunca existe)
  - Persiste IDs notificados em disco (notified.json) entre reinicializações
  - Suporta intervalos em segundos (mais preciso que minutos)
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
    CHECK_INTERVAL_SECONDS,
    MONITOR_START_TIME,
    MONITOR_END_TIME,
)
from .teams_client import check_mentions
from .telegram_sender import send_telegram, check_telegram_status

console = Console()

# Arquivo para persistir hashes de mensagens notificadas
_NOTIFIED_FILE = Path(__file__).parent.parent / "notified.json"
_MAX_NOTIFIED = 500  # evita crescimento infinito

# Arquivo de versão para rastrear mudanças de hash
_HASH_VERSION_FILE = Path(__file__).parent.parent / ".hash_version"
_HASH_VERSION = "2"  # v2 = channel::content (removido sender)


# Flag para rastrear se uma job está rodando
_job_running = False


def _check_and_migrate_hash_version() -> None:
    """
    Verifica se precisa migrar hashes de versão antiga.
    Se detectar arquivo antigo, limpa para evitar notificações duplicadas.
    """
    try:
        current = _HASH_VERSION_FILE.read_text().strip() if _HASH_VERSION_FILE.exists() else None

        if current != _HASH_VERSION:
            console.print(
                "[yellow]⚠️  Detectada mudança na função de hash (v1 → v2).[/yellow]"
            )
            console.print("[dim]  Limpando cache de menções antigas para evitar duplicatas...[/dim]")

            # Remove arquivo antigo
            if _NOTIFIED_FILE.exists():
                _NOTIFIED_FILE.unlink()

            # Marca nova versão
            _HASH_VERSION_FILE.write_text(_HASH_VERSION)
            console.print("[green]  ✅ Cache atualizado com novo hash![/green]\n")
    except Exception:
        pass


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
    """
    Gera um hash único para uma mensagem para deduplicação.
    Baseado APENAS no conteúdo (ignora canal).
    Importância: evita notificar a mesma menção 3x se ela aparecer em vários chats.
    """
    content = item.get("message", {}).get("body", {}).get("content", "")

    # Normaliza: remove espaços extras, quebras de linha, transforma em lowercase
    content_normalized = " ".join(content.split()).lower()

    # Hash por conteúdo APENAS (sem canal)
    # Garante que a mesma menção não será notificada múltiplas vezes
    return hashlib.md5(content_normalized.encode()).hexdigest()[:16]


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
    Verifica menções e envia notificações Telegram para as novas.
    """
    global _job_running

    # Evita múltiplas instâncias rodando simultaneamente
    if _job_running:
        console.print(
            "[yellow]⏳ Job anterior ainda está rodando (Teams/Playwright é lento). Aguardando...[/yellow]"
        )
        return

    _job_running = True
    try:
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
        already_notified_count = 0

        for item in mentions:
            msg_hash = _message_hash(item)
            if msg_hash in notified:
                already_notified_count += 1
                continue  # já notificamos essa mensagem

            sent = send_telegram(item["formatted_text"])
            if sent:
                notified.add(msg_hash)
                new_count += 1

        if new_count:
            _save_notified(notified)
            console.print(f"[green]✅ {new_count} nova(s) notificação(ões) enviada(s).[/green]")
            if already_notified_count > 0:
                console.print(f"[dim]  ({already_notified_count} já notificada(s))[/dim]")
        else:
            if already_notified_count > 0:
                console.print(f"[dim]  Todas as {len(mentions)} menção(ões) já foram notificadas.[/dim]")
            else:
                console.print("[dim]  Nenhuma menção nova encontrada.[/dim]")

    finally:
        _job_running = False


def start_scheduler() -> None:
    """Inicia o scheduler bloqueante."""
    # Verifica migração de hash antes de começar
    _check_and_migrate_hash_version()

    intervalo_minutos = CHECK_INTERVAL_SECONDS // 60
    intervalo_segundos = CHECK_INTERVAL_SECONDS % 60

    if intervalo_segundos > 0:
        intervalo_str = f"{intervalo_minutos}m {intervalo_segundos}s"
    else:
        intervalo_str = f"{intervalo_minutos}m"

    console.print(
        f"\n[bold]📅 Scheduler iniciado[/bold]\n"
        f"  ⏱  Intervalo: a cada {intervalo_str}\n"
        f"  🕐 Horário:   {MONITOR_START_TIME} – {MONITOR_END_TIME} (dias úteis)\n"
    )

    console.print("[bold yellow]🚀 Executando verificação inicial...[/bold yellow]")
    run_check()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(seconds=CHECK_INTERVAL_SECONDS),
        id="check_mentions",
        name="Verificar menções no Teams",
        misfire_grace_time=60,
        max_instances=1,  # ← Previne múltiplas instâncias
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]⏹  Scheduler encerrado.[/yellow]")
