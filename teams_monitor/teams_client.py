"""
Monitor Teams via Playwright — lê menções do Teams Web.

Fluxo de login melhorado:
  - Valida a sessão real no browser (não só o marker .logged_in)
  - Aguarda qualquer um dos indicadores de que Teams carregou de verdade
  - Reseta sessão automaticamente se detectar página de login após marker
  - Compatible com teams.live.com (conta pessoal Microsoft)

Extração de mensagens:
  - Usa JS para extrair remetente real e filtrar apenas mensagens de hoje
  - Fallback para extração via texto se JS não encontrar elementos structurados
"""
import re
import time
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from rich.console import Console
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .config import (
    BROWSER_SESSION_DIR,
    BROWSER_HEADLESS,
    MENTION_TARGETS,
    CHECK_INTERVAL_MINUTES,
)

console = Console()

SESSION_MARKER = BROWSER_SESSION_DIR / ".logged_in"

# Teams para conta pessoal usa teams.live.com
TEAMS_HOME_URL = "https://teams.live.com"

# ── Regex para filtrar mensagens de hoje ──────────────────────────────────────
# Mensagens de hoje mostram só HH:MM; antigas mostram data (ex: "6 de mar")
_TODAY_TIME_RE = re.compile(r'\b\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?\b')
_OLD_DATE_RE = re.compile(
    r'\b(\d{1,2}\s+de\s+\w+|ontem|yesterday|segunda|terça|quarta|quinta|sexta|'
    r'sábado|domingo|mon|tue|wed|thu|fri|sat|sun|'
    r'jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b',
    re.IGNORECASE
)

# ── JavaScript: detecta se o Teams carregou ───────────────────────────────────
_JS_IS_TEAMS_APP = """() => {
    const url = location.href;
    const isLoginPage = (
        url.includes('login.live.com') ||
        url.includes('login.microsoftonline.com') ||
        url.includes('account.live.com') ||
        (url.includes('teams.live.com') && url.includes('/login'))
    );
    if (isLoginPage) return false;

    const isTeamsApp = (
        url.includes('teams.live.com') ||
        url.includes('teams.microsoft.com')
    );
    if (!isTeamsApp) return false;

    const bodyText = document.body?.innerText?.trim() || '';
    const hasAppContent = bodyText.length > 300 || document.querySelectorAll("div[role='listitem']").length > 5; // Verifica também se há muitos itens na lista (chats)

    const hasTeamsElements = !!(
        document.querySelector('[data-tid]') ||
        document.querySelector('[class*="app-"]') ||
        document.querySelector('[id*="teams"]') ||
        document.querySelector('nav') ||
        document.querySelector('[role="main"]') ||
        document.querySelector('div[aria-label="Chats"]') || // Adiciona seletor para a lista de chats
        document.querySelector('div[role="grid"][aria-label="Conversas"]') // Adiciona seletor para a área de conversas
    );

    return hasAppContent && hasTeamsElements;
}"""

# ── JavaScript: extrai nome real do chat/grupo aberto ──────────────────────────
_JS_GET_CHAT_NAME = """() => {
    const selectors = [
        '[data-tid="chat-header-title"]',
        '[data-tid="channel-header-title"]',
        '[class*="chat-title"]',
        '[class*="chatTitle"]',
        '[class*="chatHeader"] [class*="title"]',
        '[class*="channel-name"]',
        '[class*="channelName"]',
        'h1', 'h2',
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        const t = el?.innerText?.trim();
        if (t && t.length > 0 && t.length < 100) return t;
    }
    // Fallback: tenta o título da aba ou página
    const title = document.title || '';
    if (title && !title.toLowerCase().includes('microsoft')) return title.split('|')[0].trim();
    return null;
}"""

# ── JavaScript: extrai mensagens estruturadas com remetente e filtro de hoje ──
_JS_GET_MESSAGES = """() => {
    const todayDate = new Date().toISOString().slice(0, 10); // "2026-03-07"
    const todayRe = /^\\d{1,2}:\\d{2}(\\s*(AM|PM|am|pm))?$/; // HH:MM sem data (fallback)
    const results = [];

    // Tenta extrair {sender, content, time} de elementos por vários seletores
    const authorSelectors = [
        '[data-tid="message-author-name"]',
        '[class*="author-name"]',
        '[class*="authorName"]',
        '[class*="AuthorName"]',
        '[class*="senderName"]',
        '[class*="SenderName"]',
        '[class*="displayName"]',
        '[class*="person-name"]',
        '[class*="personName"]',
    ];

    for (const authorSel of authorSelectors) {
        const authorEls = document.querySelectorAll(authorSel);
        if (!authorEls.length) continue;

        authorEls.forEach(authorEl => {
            const sender = authorEl.innerText?.trim();
            if (!sender || sender.length > 80) return;

            const container = authorEl.closest(
                '[data-tid], [class*="message"], [class*="Message"], [class*="thread-item"]'
            ) || authorEl.parentElement?.parentElement;
            if (!container) return;

            // Busca timestamp — prefere o atributo datetime ISO (data completa)
            const timeEl = container.querySelector(
                'time, [class*="timestamp"], [class*="Timestamp"], [class*="message-time"]'
            );
            const dtAttr = timeEl?.getAttribute('datetime') || '';
            const timeText = timeEl?.getAttribute('title') ||
                             timeEl?.innerText?.trim() || '';

            // Verifica se é de hoje:
            // 1º tenta pelo atributo datetime ISO (mais confiável)
            // 2º fallback: innerText só com HH:MM
            const isToday = dtAttr ? dtAttr.startsWith(todayDate)
                                   : todayRe.test(timeText);

            if (!isToday) return;

            // Busca conteúdo
            const contentEls = container.querySelectorAll(
                'p, [data-tid="message-body"], [class*="message-body"], [class*="messageBody"],' +
                '[class*="message-text"], [class*="messageText"]'
            );
            const content = Array.from(contentEls)
                .map(el => el.innerText?.trim())
                .filter(t => t && t !== sender && t.length > 1)
                .join(' ');

            if (content.length > 2) {
                results.push({
                    sender,
                    content: content.slice(0, 500),
                    time: timeText,
                    isToday: true,
                });
            }
        });

        if (results.length > 0) break;
    }

    // Deduplica por prefixo do conteúdo
    const seen = new Set();
    return results.filter(r => {
        const k = r.content.slice(0, 50);
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
    });
}"""


# ── Utilidades ─────────────────────────────────────────────────────────────────

# Regex para @menção ("@Vinicius", "@Vinicius Campos")
_AT_MENTION_RE_CACHE: dict[str, re.Pattern] = {}

def _get_mention_patterns() -> list[re.Pattern]:
    """Retorna regexes que detectam @mencao para cada target."""
    patterns = []
    for target in MENTION_TARGETS:
        key = target
        if key not in _AT_MENTION_RE_CACHE:
            # Aceita @Nome, @Nome Sobrenome, <@...>, spans com o nome
            escaped = re.escape(target)
            _AT_MENTION_RE_CACHE[key] = re.compile(
                rf'@{escaped}',
                re.IGNORECASE
            )
        patterns.append(_AT_MENTION_RE_CACHE[key])
    return patterns


def _is_mentioned(text: str) -> bool:
    """True se o texto contém @Nome do alvo monitorado."""
    for p in _get_mention_patterns():
        if p.search(text):
            return True
    return False


def _format_message(sender: str, body: str, context_name: str) -> str:
    if len(body) > 300:
        body = body[:297] + "..."
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"🔔 *Menção no Teams!*\n\n"
        f"👤 *De:* {sender}\n"
        f"💬 *Em:* {context_name}\n"
        f"🕐 *Horário:* {ts}\n\n"
        f"📝 *Mensagem:*\n{body}"
    )


def _save_debug_screenshot(page, name="debug_teams.png"):
    try:
        page.screenshot(path=name, full_page=False)
        console.print(f"[dim]  📸 Screenshot salva: {name}[/dim]")
    except Exception:
        pass


def _get_full_text(page) -> str:
    """Extrai todo o texto visível da página."""
    texts = []
    for ctx in [page] + page.frames:
        try:
            t = ctx.evaluate("() => document.body?.innerText || ''")
            if t:
                texts.append(t)
        except Exception:
            pass
    return "\n".join(texts)


def _filter_today_text(text: str) -> str:
    """
    Retorna apenas o bloco de texto após o separador 'Hoje' do Teams.
    O Teams PT-BR usa 'Hoje' como cabeçalho de seção para mensagens do dia atual.
    Se não encontrar 'Hoje', retorna string vazia (sem mensagens de hoje).
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Busca marcador de seção do Teams para hoje
    # PT-BR: "Hoje" / EN: "Today" — pode vir com horário: "Hoje 20:25"
    HOJE_RE = re.compile(r'^(hoje|today)\b', re.IGNORECASE)

    hoje_idx = None
    for i, line in enumerate(lines):
        if HOJE_RE.match(line):
            hoje_idx = i
            break

    if hoje_idx is not None:
        return '\n'.join(lines[hoje_idx + 1:])

    # Nenhum separador 'Hoje' encontrado = sem mensagens de hoje
    return ''


# ── Sessão ─────────────────────────────────────────────────────────────────────

def _reset_session():
    """Remove browser_session completamente (sessão corrompida ou logout)."""
    if BROWSER_SESSION_DIR.exists():
        shutil.rmtree(BROWSER_SESSION_DIR)
        console.print("[yellow]  🗑  Sessão anterior removida[/yellow]")
    BROWSER_SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _is_session_valid() -> bool:
    """
    Abre o browser brevemente para checar se a sessão salva ainda está logada.
    Retorna True se o Teams abrir sem redirecionar para login.
    """
    if not SESSION_MARKER.exists():
        return False

    console.print("[dim]  🔎 Validando sessão salva...[/dim]")
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_SESSION_DIR),
                headless=True,  # sempre headless para validação rápida
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(TEAMS_HOME_URL, wait_until="domcontentloaded", timeout=25_000)
                try:
                    page.wait_for_function(_JS_IS_TEAMS_APP, timeout=20_000)
                    console.print("[green]  ✅ Sessão válida![/green]")
                    return True
                except PWTimeout:
                    current_url = page.url
                    console.print(f"[yellow]  ⚠️  Sessão inválida. URL atual: {current_url[:80]}[/yellow]")
                    return False
            finally:
                ctx.close()
    except Exception as e:
        console.print(f"[yellow]  ⚠️  Erro ao validar sessão: {e}[/yellow]")
        return False


def ensure_logged_in() -> bool:
    """
    Garante que há uma sessão válida do Teams.
    - Se tem sessão válida no browser: retorna True rapidamente
    - Se não tem sessão ou ela expirou: abre janela para o usuário logar
    """
    if _is_session_valid():
        return True

    SESSION_MARKER.unlink(missing_ok=True)
    _reset_session()

    console.print("\n[bold yellow]🔐 Login necessário no Teams Web[/bold yellow]")
    console.print("  👉 O browser vai abrir — faça login com sua conta Microsoft")
    console.print("  💡 Use sua conta pessoal (Hotmail/Outlook/Live)\n")

    BROWSER_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    success = False

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_SESSION_DIR),
            headless=True,  # sempre headless no ambiente de sandbox
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        console.print(f"  🌐 Abrindo {TEAMS_HOME_URL}...")
        page.goto(TEAMS_HOME_URL, wait_until="domcontentloaded", timeout=30_000)

        console.print("[bold cyan]  ⏳ Aguardando você fazer login (até 5 minutos)...[/bold cyan]")
        console.print("  📌 Após o Teams carregar completamente, aguarde alguns segundos.\n")

        try:
            page.wait_for_function(_JS_IS_TEAMS_APP, timeout=300_000)
            console.print("[green]  ✅ Teams detectado! Aguardando estabilizar (10s)...[/green]")
            page.wait_for_timeout(10_000)

            _save_debug_screenshot(page, "login_success.png")

            SESSION_MARKER.touch()
            console.print("[bold green]  ✅ Login bem-sucedido! Sessão salva.\n[/bold green]")
            success = True

        except PWTimeout:
            console.print("[red]  ❌ Timeout de 5 minutos. A sessão não foi validada. Por favor, faça login manualmente no Teams Web e tente novamente.[/red]")
            _save_debug_screenshot(page, "login_timeout.png")
        finally:
            ctx.close()

    return success


# ── Monitor ────────────────────────────────────────────────────────────────────

def check_mentions(since_minutes: int | None = None) -> list[dict]:
    """Abre o Teams Web, navega pelos chats e busca menções de hoje."""
    if since_minutes is None:
        since_minutes = CHECK_INTERVAL_MINUTES + 2

    if not ensure_logged_in():
        return []

    console.print("[cyan]🔍 Verificando menções no Teams Web...[/cyan]")

    found = []

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_SESSION_DIR),
            headless=BROWSER_HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            # Abre o Teams
            page.goto(TEAMS_HOME_URL, wait_until="domcontentloaded", timeout=25_000)

            # Aguarda o app carregar de verdade
            console.print("  ⏳ Aguardando Teams carregar...")
            try:
                page.wait_for_function(_JS_IS_TEAMS_APP, timeout=30_000)
                console.print(f"  ✅ Teams carregado em: {page.url[:60]}")
            except PWTimeout:
                console.print("[red]  ❌ Teams não carregou (possível sessão expirada). Resetando...[/red]")
                _save_debug_screenshot(page, "check_timeout.png")
                ctx.close()
                SESSION_MARKER.unlink(missing_ok=True)
                _reset_session()
                return []

            _save_debug_screenshot(page, "debug_teams.png")

            # Navega pelos chats
            found.extend(_iterate_chats(page))

        except Exception as e:
            console.print(f"[red]  ❌ Erro: {e}[/red]")
            _save_debug_screenshot(page, "debug_error.png")
        finally:
            ctx.close()

    # Deduplica
    seen, unique = set(), []
    for f in found:
        k = f["message"]["body"]["content"][:80]
        if k not in seen:
            seen.add(k)
            unique.append(f)

    if unique:
        console.print(f"[bold green]🎯 {len(unique)} menção(ões) de hoje encontrada(s)![/bold green]")
    else:
        console.print("[dim]  Nenhuma menção nova encontrada.[/dim]")

    return unique


# ── JavaScript: busca @menções reais via DOM ─────────────────────────────────
_JS_GET_MENTIONS_IN_CHAT = """(targetNames) => {
    // targetNames: ["Vinicius Campos", ...]
    const results = [];
    const todayDate = new Date().toISOString().slice(0, 10);

    // 1. Busca elementos de @menção reais (Teams renderiza com classe 'mention')
    const mentionEls = document.querySelectorAll(
        '[class*="mention"], [data-mention], [class*="at-mention"], ' +
        '[class*="atMention"], span[title], [itemtype*="mention"]'
    );

    const mentionedTargets = new Set();
    mentionEls.forEach(el => {
        const name = el.innerText?.trim().replace(/^@/, '') || '';
        const title = el.getAttribute('title') || el.getAttribute('data-mention') || '';
        const candidate = (name + ' ' + title).toLowerCase();
        targetNames.forEach(t => {
            if (candidate.includes(t.toLowerCase())) {
                mentionedTargets.add(t);
            }
        });
    });

    // 2. Para cada @menção encontrada, pega a mensagem pai + remetente + timestamp
    mentionEls.forEach(el => {
        const name = (el.innerText?.trim() || '').replace(/^@/, '');
        const isTarget = targetNames.some(t =>
            name.toLowerCase().includes(t.toLowerCase())
        );
        if (!isTarget) return;

        // Sobe na árvore para encontrar o container da mensagem
        const msgContainer = el.closest(
            '[data-tid^="message"], [class*="message"], [class*="Message"], ' +
            '[class*="thread-item"], [class*="ThreadItem"]'
        );
        if (!msgContainer) return;

        // Verificar se é de hoje
        const timeEl = msgContainer.querySelector(
            'time, [class*="timestamp"], [class*="Timestamp"]'
        );
        const dtAttr = timeEl?.getAttribute('datetime') || '';
        if (dtAttr && !dtAttr.startsWith(todayDate)) return;

        // Remetente
        const authorEl = msgContainer.querySelector(
            '[data-tid="message-author-name"], [class*="author"], [class*="Author"], ' +
            '[class*="sender"], [class*="Sender"], [class*="displayName"]'
        );
        const sender = authorEl?.innerText?.trim() || '?';

        // Conteúdo completo da mensagem
        const bodyEl = msgContainer.querySelector(
            '[data-tid="message-body"], [class*="message-body"], ' +
            '[class*="messageBody"], [class*="message-text"]'
        );
        const content = bodyEl?.innerText?.trim() || msgContainer.innerText?.trim() || '';

        if (content.length > 2) {
            results.push({
                sender,
                content: content.slice(0, 500),
                time: timeEl?.innerText?.trim() || '',
            });
        }
    });

    // 3. Fallback: varre todo o texto de mensagens de hoje e busca @nome
    if (results.length === 0) {
        const bodyEls = document.querySelectorAll(
            '[data-tid="message-body"], [class*="message-body"], [class*="messageBody"], p'
        );
        bodyEls.forEach(bodyEl => {
            const text = bodyEl.innerText?.trim() || '';
            const isTarget = targetNames.some(t =>
                text.toLowerCase().includes('@' + t.split(' ')[0].toLowerCase()) ||
                text.toLowerCase().includes('@' + t.toLowerCase())
            );
            if (!isTarget || text.length < 2) return;

            const msgContainer = bodyEl.closest(
                '[data-tid^="message"], [class*="message"], [class*="thread-item"]'
            );
            const timeEl = msgContainer?.querySelector(
                'time, [class*="timestamp"]'
            );
            const dtAttr = timeEl?.getAttribute('datetime') || '';
            if (dtAttr && !dtAttr.startsWith(todayDate)) return;

            const authorEl = msgContainer?.querySelector(
                '[data-tid="message-author-name"], [class*="author"], [class*="sender"]'
            );
            results.push({
                sender: authorEl?.innerText?.trim() || '?',
                content: text.slice(0, 500),
                time: timeEl?.innerText?.trim() || '',
            });
        });
    }

    // Deduplica
    const seen = new Set();
    return results.filter(r => {
        const k = r.content.slice(0, 60);
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
    });
}"""

def _extract_mentions_structured(items: list[dict], context: str) -> list[dict]:
    """Extrai menções de itens estruturados {sender, content, time}."""
    found = []
    for item in items:
        content = item.get("content", "")
        sender = item.get("sender", "?")
        # O JS já filtra apenas as menções reais do usuário através do DOM.
        # Não exigimos _is_mentioned() aqui pois o Teams pode esconder o '@' no texto renderizado.
        if 5 < len(content) < 500:
            found.append({
                "team": "Teams Web",
                "channel": context,
                "message": {"body": {"content": content}, "from": {"user": {"displayName": sender}}},
                "formatted_text": _format_message(sender, content, context),
            })
    return found


def _extract_mentions_from_text(text: str, context: str) -> list[dict]:
    """Extrai menções de texto puro (fallback). Filtra apenas mensagens de hoje."""
    # Filtra só mensagens de hoje
    today_text = _filter_today_text(text)
    found = []
    lines = [l.strip() for l in today_text.split("\n") if l.strip()]
    for line in lines:
        if _is_mentioned(line) and 5 < len(line) < 400:
            found.append({
                "team": "Teams Web",
                "channel": context,
                "message": {"body": {"content": line}, "from": {"user": {"displayName": "?"}}},
                "formatted_text": _format_message("?", line, context),
            })
    return found


def _iterate_chats(page) -> list[dict]:
    """Clica em cada chat, scrolla para mensagens recentes e busca @menções de hoje."""
    found = []

    # Seletores da lista de chats no Teams pessoal
    CHAT_LIST_SELECTORS = [
        '[data-tid="chat-list-item"]',
        '[data-testid="chat-list-item"]',
        '[role="listitem"]',
        '#chat-list [role="option"]',
        '.chat-list-container [role="option"]',
        '[class*="chatList"] [role="option"]',
        '[class*="chat-item"]',
    ]

    chat_items = []
    for sel in CHAT_LIST_SELECTORS:
        try:
            items = page.query_selector_all(sel)
            if len(items) > 0:
                chat_items = items[:15]  # verifica até 15 chats
                console.print(f"  💬 {len(chat_items)} chat(s) encontrado(s)")
                break
        except Exception:
            pass

    if not chat_items:
        console.print("[dim]  Lista de chats não encontrada — lendo texto da tela[/dim]")
        full_text = _get_full_text(page)
        return _extract_mentions_from_text(full_text, "Teams")

    # Nomes alvo para passar ao JS
    target_names = list(MENTION_TARGETS)

    for i, item in enumerate(chat_items):
        try:
            item.click()
            page.wait_for_timeout(2_000)

            # Tenta pegar o nome real do chat via JS
            try:
                chat_name = page.evaluate(_JS_GET_CHAT_NAME)
            except Exception:
                chat_name = None

            if not chat_name:
                raw = item.inner_text() if item else f"Chat {i+1}"
                chat_name = raw.split("\n")[0].strip()[:80] or f"Chat {i+1}"

            console.print(f"  📂 Verificando: [bold]{chat_name}[/bold]")

            # Scrolla para o final (mensagens mais recentes)
            try:
                page.evaluate("""
                    () => {
                        const scroller = document.querySelector(
                            '[class*="message-list"], [class*="messageList"],'
                            + '[class*="chat-pane"], [role="log"], '
                            + '[class*="scrollable"]'
                        );
                        if (scroller) scroller.scrollTop = scroller.scrollHeight;
                        else window.scrollTo(0, document.body.scrollHeight);
                    }
                """)
                page.wait_for_timeout(1_000)
            except Exception:
                pass

            # 1. Tenta JS especializado em @menções reais do Teams DOM
            try:
                structured = page.evaluate(_JS_GET_MENTIONS_IN_CHAT, target_names)
            except Exception:
                structured = None

            if structured:
                mentions = _extract_mentions_structured(structured, chat_name)
                if mentions:
                    console.print(f"  🎯 {len(mentions)} @menção(ões) hoje em '[bold]{chat_name}[/bold]'")
                    found.extend(mentions)
            else:
                # 2. Fallback: texto filtrado por hoje + busca @nome
                full_text = _get_full_text(page)
                mentions = _extract_mentions_from_text(full_text, chat_name)
                if mentions:
                    console.print(f"  🎯 {len(mentions)} @menção(ões) hoje em '[bold]{chat_name}[/bold]'")
                    found.extend(mentions)

        except Exception as e:
            console.print(f"[dim]  ⚠️ Erro ao verificar chat {i+1}: {e}[/dim]")
            continue

    return found
