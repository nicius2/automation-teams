"""
Ponto de entrada principal da automação Teams → Telegram.

Uso:
    python main.py                   # Inicia o monitor completo
    python main.py --test-tg         # Envia mensagem de teste via Telegram
    python main.py --get-chat-id     # Descobre seu chat_id do Telegram
    python main.py --check-now       # Faz uma verificação manual agora
    python main.py --clear-cache     # Limpa cache de menções já notificadas (para debug)
"""
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()
BASE_DIR = Path(__file__).parent


def print_banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]🤖 Teams → Telegram Automation[/bold cyan]\n"
        "[dim]Monitora menções no Teams e notifica via Telegram[/dim]",
        border_style="cyan",
    ))


def main() -> None:
    print_banner()
    args = sys.argv[1:]

    # ── Modo: descobre chat_id ──────────────────────────────────────────────────
    if "--get-chat-id" in args:
        from teams_monitor.telegram_sender import get_my_chat_id
        console.print("\n[bold]🔍 Buscando seu chat_id no Telegram...[/bold]")
        console.print("[dim]  (Envie uma mensagem ao seu bot antes de rodar isso)[/dim]")
        chat_id = get_my_chat_id()
        if chat_id:
            console.print(f"[green]✅ Seu chat_id é: [bold]{chat_id}[/bold][/green]")
            console.print(f"[dim]  Adicione ao .env:  TELEGRAM_CHAT_ID={chat_id}[/dim]")
        else:
            console.print("[red]❌ Não encontrei chat_id. Envie uma mensagem ao bot e tente novamente.[/red]")
        return

    # ── Modo: teste Telegram ────────────────────────────────────────────────────
    if "--test-tg" in args or "--test-telegram" in args:
        from teams_monitor.telegram_sender import send_telegram
        console.print("\n[bold]📨 Enviando mensagem de teste via Telegram...[/bold]")
        ok = send_telegram(
            "✅ *Teste de automação!*\n\n"
            "Se você recebeu isso, a integração Teams → Telegram está funcionando! 🎉"
        )
        if ok:
            console.print("[green]✅ Mensagem enviada! Verifique seu Telegram.[/green]")
        else:
            console.print("[red]❌ Falha. Verifique TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env[/red]")
        return

    # ── Modo: limpar cache de deduplicação ───────────────────────────────────────
    if "--clear-cache" in args or "--reset-cache" in args:
        NOTIFIED_FILE = BASE_DIR / "notified.json"
        if NOTIFIED_FILE.exists():
            NOTIFIED_FILE.unlink()
            console.print("[green]✅ Cache de menções notificadas foi apagado![/green]")
            console.print("[dim]  Na próxima execução, você receberá todas as menções de hoje novamente.[/dim]")
        else:
            console.print("[yellow]ℹ️  Nenhum cache para limpar.[/yellow]")
        return

    # ── Modo: verificação manual imediata ──────────────────────────────────────
    if "--check-now" in args:
        import json, hashlib
        from teams_monitor.teams_client import check_mentions
        from teams_monitor.telegram_sender import send_telegram
        NOTIFIED_FILE = BASE_DIR / "notified.json"
        HASH_VERSION_FILE = BASE_DIR / ".hash_version"
        HASH_VERSION = "2"

        # Verifica migração de hash
        def _check_migration():
            try:
                current = HASH_VERSION_FILE.read_text().strip() if HASH_VERSION_FILE.exists() else None
                if current != HASH_VERSION:
                    console.print("[yellow]⚠️  Detectada mudança na função de hash (v1 → v2).[/yellow]")
                    console.print("[dim]  Limpando cache de menções antigas para evitar duplicatas...[/dim]")
                    if NOTIFIED_FILE.exists():
                        NOTIFIED_FILE.unlink()
                    HASH_VERSION_FILE.write_text(HASH_VERSION)
                    console.print("[green]  ✅ Cache atualizado com novo hash!\n[/green]")
            except Exception:
                pass

        _check_migration()

        def _load() -> set:
            try:
                if NOTIFIED_FILE.exists():
                    return set(json.loads(NOTIFIED_FILE.read_text()))
            except Exception:
                pass
            return set()

        def _save(s: set) -> None:
            try:
                items = list(s)[-500:]
                NOTIFIED_FILE.write_text(json.dumps(items))
            except Exception:
                pass

        def _hash(item: dict) -> str:
            content = item.get("message", {}).get("body", {}).get("content", "")

            # Normaliza: remove espaços extras, quebras de linha, transforma em lowercase
            content_normalized = " ".join(content.split()).lower()

            # Hash por conteúdo APENAS (sem canal/sender)
            # Garante que a mesma menção não seja notificada múltiplas vezes
            return hashlib.md5(content_normalized.encode()).hexdigest()[:16]

        console.print("\n[bold]🔍 Verificação manual (mensagens de hoje)...[/bold]")
        results = check_mentions()
        notified = _load()
        new_count = 0

        for item in results:
            h = _hash(item)
            if h in notified:
                continue
            ok = send_telegram(item["formatted_text"])
            if ok:
                notified.add(h)
                new_count += 1

        _save(notified)
        if new_count:
            console.print(f"[green]✅ {new_count} mensagem(ns) nova(s) enviada(s) ao Telegram.[/green]")
        elif results:
            console.print("[yellow]Todas as menções de hoje já foram notificadas anteriormente.[/yellow]")
        else:
            console.print("[yellow]Nenhuma menção encontrada hoje.[/yellow]")
        return

    # ── Modo padrão: inicia o scheduler ───────────────────────────────────────
    from teams_monitor.telegram_sender import check_telegram_status
    if not check_telegram_status():
        console.print("[red]❌ Bot do Telegram inacessível ou token inválido.[/red]")
        console.print("[dim]  Verifique TELEGRAM_BOT_TOKEN no .env[/dim]")
        sys.exit(1)

    from teams_monitor.scheduler import start_scheduler
    start_scheduler()


if __name__ == "__main__":
    main()
