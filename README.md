# Teams → Telegram Automation 🤖

Monitora **menções no Microsoft Teams Web** e envia **notificações em tempo real pelo Telegram**.

---

## 🏗️ Arquitetura

```
Scheduler (APScheduler)
  ↓
Teams Web Monitor (Playwright)
  ├── Detecta @menções reais
  ├── Filtra apenas mensagens de hoje
  ├── Deduplicação robusta
  └── Envia via Telegram Bot
```

---

## 📋 Pré-requisitos

- **Python ≥ 3.10** — [download](https://python.org/)
- **Conta Microsoft** (pessoal: Hotmail/Outlook/Live)
- **Bot do Telegram** (gratuito)

---

## ⚙️ Passo 1 — Criar Bot do Telegram (gratuito)

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome para o bot (ex: `teams-monitor-bot`)
4. Copie o **token** fornecido (algo como `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
5. Adicione ao `.env` como `TELEGRAM_BOT_TOKEN=seu_token_aqui`

### Descobrir seu Chat ID

1. Envie qualquer mensagem para o seu bot
2. Execute:
   ```bash
   python main.py --get-chat-id
   ```
3. Copie o `TELEGRAM_CHAT_ID` exibido

---

## ⚙️ Passo 2 — Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env`:

```env
# Bot do Telegram
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
TELEGRAM_REQUEST_TIMEOUT=20

# Configurações do Monitor
MENTION_TARGETS=Vinicius Campos     # Nome(s) para monitorar (case-insensitive)
MONITOR_START_TIME=08:00             # Início do monitoramento
MONITOR_END_TIME=23:00               # Fim do monitoramento
CHECK_INTERVAL_SECONDS=30            # Verificar a cada 30 segundos

# Browser
BROWSER_HEADLESS=true                # true = background silencioso
```

---

## ⚙️ Passo 3 — Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 🚀 Passo 4 — Uso

### Modo: Monitoramento contínuo (recomendado)

```bash
python main.py
```

**Na primeira execução:**
1. O navegador abre automaticamente
2. Faça login na sua conta Microsoft
3. O sistema salva a sessão
4. Próximas execuções rodam em **background** (sem interface gráfica)

### Modo: Teste manual (sem agenda)

```bash
# Verifica menções agora
python main.py --check-now

# Envia mensagem de teste
python main.py --test-tg

# Descobre seu Chat ID
python main.py --get-chat-id

# Limpa cache de menções (debug)
python main.py --clear-cache
```

---

## 🚀 Autostart — Executar ao iniciar o PC

### Windows

#### **Opção 1: Tarefa Agendada (recomendado)**

1. Abra **Agendador de Tarefas** (pesquise no menu Iniciar)
2. Clique em **Criar Tarefa Básica**
3. Preencha:
   - **Nome:** `Teams Automation`
   - **Descrição:** `Monitora menções do Teams e notifica via Telegram`
4. Clique em **Próximo**
5. **Gatilho:**
   - Selecione **"Ao iniciar o computador"**
   - Clique em **Próximo**
6. **Ação:**
   - Selecione **"Iniciar um programa"**
   - **Programa/script:** `C:\Python313\python.exe` (ajuste para sua versão Python)
   - **Adicionar argumentos:** `main.py`
   - **Iniciar em:** `C:\Users\SEU_USUARIO\Documents\Desafio-Semanal\semana_3\teams-automation`
7. Clique em **Próximo** e depois **Concluir**

#### **Opção 2: Pasta Inicialização (mais simples)**

1. Crie um arquivo `teams-automation.bat` na raiz do projeto:

```batch
@echo off
cd /d "%~dp0"
python main.py
pause
```

2. Copie esse arquivo para a pasta de Inicialização:
   ```
   C:\Users\SEU_USUARIO\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\
   ```

3. Próxima vez que reiniciar, o script executa automaticamente

### Linux / Ubuntu

#### **Opção 1: Serviço systemd (recomendado)**

1. Crie o arquivo de serviço:
   ```bash
   sudo nano /etc/systemd/system/teams-automation.service
   ```

2. Copie o conteúdo:
   ```ini
   [Unit]
   Description=Teams → Telegram Automation
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=seu_usuario
   WorkingDirectory=/home/seu_usuario/Documents/Desafio-Semanal/semana_3/teams-automation
   ExecStart=/usr/bin/python3 main.py
   Restart=on-failure
   RestartSec=30
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```

3. Salve com `Ctrl+O` e depois `Ctrl+X`

4. Habilite o serviço:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable teams-automation
   sudo systemctl start teams-automation
   ```

5. Verifique o status:
   ```bash
   sudo systemctl status teams-automation
   ```

#### **Opção 2: Cron Job (alternativa)**

1. Abra o crontab:
   ```bash
   crontab -e
   ```

2. Adicione a linha:
   ```cron
   @reboot cd /home/seu_usuario/Documents/Desafio-Semanal/semana_3/teams-automation && /usr/bin/python3 main.py &
   ```

3. Salve e saia (`:wq` no editor)

---

## 📊 Fluxo de detecção de menções

```
1. Scanner DOM → Identifica elementos de @menção reais (não texto genérico)
                   ↓
2. Filtro por data → Apenas mensagens de HOJE (horário local)
                   ↓
3. Deduplicação JS → Remove duplicatas dentro do mesmo chat
                   ↓
4. Deduplicação Python → Remove se já foi notificado (hash por conteúdo)
                   ↓
5. Envio Telegram → Uma notificação por menção única
```

---

## 🔔 Formato de notificação Telegram

```
🔔 MENÇÃO NO TEAMS!

━━━━━━━━━━━━━━━━━━━━
👤 Quem: João Silva
📍 Onde: Departamento de TI
🕐 Quando: 12/03/2026 17:30
━━━━━━━━━━━━━━━━━━━━

💬 Mensagem:
Oi Vinicius, pode revisar esse código?

━━━━━━━━━━━━━━━━━━━━
```

---

## 🏗️ Estrutura do projeto

```
teams-automation/
├── main.py                    # Ponto de entrada
├── requirements.txt           # Dependências Python
├── README.md                  # Este arquivo
├── .env                       # Suas credenciais (não commitar!)
├── .env.example               # Template de configuração
├── notified.json              # Cache de menções já notificadas
├── .hash_version              # Versão do algoritmo de hash
├── browser_session/           # Sessão do Teams (gerada automaticamente)
├── teams_monitor/
│   ├── config.py              # Carregamento de configurações
│   ├── teams_client.py        # Playwright + detecção de menções
│   ├── telegram_sender.py     # Envio via API Telegram
│   └── scheduler.py           # Agendador (APScheduler)
└── test_mention_detection.py  # Testes de detecção
```

---

## 🔧 Troubleshooting

### "Teams não carregou" / Timeout

```bash
# Limpe a sessão e faça login novamente
rm -rf browser_session/
python main.py
```

### "Sessão expirada"

O sistema detecta e pede login automaticamente:

```bash
# Aguarde a janela do navegador abrir e faça login
python main.py
```

### "Telegram não acessível"

```bash
# Teste a conexão
python main.py --test-tg

# Se falhar, verifique:
# 1. TELEGRAM_BOT_TOKEN correto em .env
# 2. Conexão com internet
# 3. Bot criado em @BotFather
```

### "Recebendo notificações antigas"

O sistema já filtra apenas mensagens de hoje, mas você pode limpar o cache:

```bash
python main.py --clear-cache
```

---

## ⚠️ Avisos importantes

- **Sessão do Teams** é salva em `browser_session/` — **não compartilhe essa pasta**
- **Token Telegram** é salvo em `.env` — **não commitar esse arquivo**
- O `.gitignore` já está configurado para ignorar esses arquivos
- A detecção **APENAS** notifica @menções reais, não mencionar o nome casualmente
- Mensagens são filtradas por data local (não UTC)

---

## 📝 Logging e Debug

Para ver logs detalhados:

```bash
# Linux/Ubuntu
sudo journalctl -u teams-automation -f

# Ou rode manualmente:
python main.py

# Ativa debug no console
python main.py --check-now
```

---

## 🤝 Contribuições

Próximas melhorias:
- [ ] Suporte para múltiplos bots/chats
- [ ] Interface web de configuração
- [ ] Notificações de reações e respostas
- [ ] Histórico de menções

---

## 📄 Licença

MIT — uso livre para fins pessoais e comerciais.

---

**Desenvolvido com ❤️ em Python + Playwright + Telegram**
