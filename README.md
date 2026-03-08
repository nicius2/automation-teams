# Teams → WhatsApp Automation 🤖

Automação que monitora mensagens no Microsoft Teams com **@Jose** e envia notificações pelo **WhatsApp** (usando Baileys — gratuito, sem custo de API).

---

## 🏗️ Arquitetura

```
Python Scheduler (APScheduler)
  └── Teams Monitor (Microsoft Graph API)
        └── WhatsApp Sender → Baileys Server (Node.js) → WhatsApp
```

---

## 📋 Pré-requisitos

- **Node.js ≥ 17** — [download](https://nodejs.org/)
- **Python ≥ 3.10** — [download](https://python.org/)
- **Conta Microsoft 365** com acesso ao Teams
- **Conta Azure** gratuita para registrar o app (não cobra nada)

---

## ⚙️ Passo 1 — Registrar app no Azure (gratuito)

> Isso dá permissão ao script de ler suas mensagens do Teams.

1. Acesse [portal.azure.com](https://portal.azure.com) e faça login com sua conta Microsoft
2. Busque por **"App registrations"** e clique em **"New registration"**
3. Preencha:
   - **Name:** `Teams Automation`
   - **Supported account types:** _Accounts in any organizational directory and personal Microsoft accounts_
   - **Redirect URI:** deixe em branco
4. Clique em **Register**
5. Anote o **Application (client) ID** e o **Directory (tenant) ID** da tela de overview

### Adicionar permissões

1. No menu lateral, vá em **API permissions → Add a permission → Microsoft Graph**
2. Escolha **Delegated permissions** e adicione:
   - `ChannelMessage.Read.All`
   - `Chat.Read`
   - `Team.ReadBasic.All`
3. Clique em **Grant admin consent** (ou peça para o admin do tenant)

---

## ⚙️ Passo 2 — Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env`:

```env
AZURE_CLIENT_ID=seu_client_id_aqui
AZURE_TENANT_ID=seu_tenant_id_aqui
WHATSAPP_TARGET_PHONE=5511999998888   # seu número com DDI+DDD
MENTION_TARGETS=jose                  # nomes a monitorar
MONITOR_START_TIME=08:00
MONITOR_END_TIME=18:00
CHECK_INTERVAL_MINUTES=5
```

---

## ⚙️ Passo 3 — Instalar dependências

```bash
# Servidor WhatsApp (Baileys)
cd whatsapp-server
npm install
cd ..

# Monitor Python
pip install -r requirements.txt
```

---

## 🚀 Passo 4 — Uso

### Opção A — Tudo de uma vez (recomendado)

```bash
python main.py
```

Na primeira execução:
1. O servidor Baileys abre — **escaneie o QR code** com seu WhatsApp  
   *(Configurações → Dispositivos Vinculados → Vincular dispositivo)*
2. Uma janela do browser abre pedindo login Microsoft — faça login uma vez
3. A automação começa a monitorar! ✅

### Opção B — Comandos individuais de teste

```bash
# Testa só autenticação Microsoft
python main.py --auth-only

# Testa envio WhatsApp (servidor Baileys precisa estar rodando)
python main.py --test-wa

# Verificação manual das últimas 24h
python main.py --check-now

# Inicia só o servidor Baileys (em outro terminal)
cd whatsapp-server && node server.js
```

---

## 📱 Como funciona o WhatsApp (Baileys)

O [Baileys](https://github.com/WhiskeySockets/Baileys) conecta ao WhatsApp Web via WebSocket — **o mesmo protocolo do navegador**. É gratuito e usa sua conta pessoal do WhatsApp.

- Na primeira execução: **QR code** no terminal → escaneie uma vez
- A sessão fica salva em `whatsapp-server/auth_info/` — não precisa escanear de novo
- Se desconectar: delete a pasta `auth_info/` e escaneie novamente

---

## 📌 Estrutura do projeto

```
teams-automation/
├── main.py                    # Ponto de entrada
├── requirements.txt           # Dependências Python
├── .env.example               # Template de configuração
├── .env                       # Suas credenciais (não commitar!)
├── teams_monitor/
│   ├── config.py              # Configurações
│   ├── teams_client.py        # Graph API + detecção de menções
│   ├── whatsapp_sender.py     # Envio via Baileys
│   └── scheduler.py           # Agendador de tarefas
└── whatsapp-server/
    ├── package.json
    ├── server.js              # Servidor Baileys REST
    └── auth_info/             # Sessão WhatsApp (gerado automaticamente)
```

---

## 🔔 Exemplo de notificação recebida

```
🔔 Menção @Jose no Teams!

👤 De: Maria Silva
🏢 Time: Empresa ABC
💬 Canal: geral
🕐 Horário: 05/03/2026 09:15

📝 Mensagem:
@Jose pode revisar o relatório de vendas?
```

---

## 🛑 Executar automaticamente ao ligar o PC (Linux)

Crie um arquivo de serviço systemd para iniciar automaticamente:

```bash
# Crie o arquivo de serviçor
sudo nano /etc/systemd/system/teams-automation.service
```

```ini
[Unit]
Description=Teams WhatsApp Automation
After=network.target

[Service]
Type=simple
User=SEU_USUARIO
WorkingDirectory=/home/SEU_USUARIO/Documents/Desafio-Semanal/semana_3/teams-automation
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable teams-automation
sudo systemctl start teams-automation
```

---

## ⚠️ Avisos importantes

- **Baileys** usa o protocolo do WhatsApp Web — funciona para uso pessoal, mas não é a API oficial
- O token Microsoft é salvo localmente em `.token_cache.json` — não compartilhe
- Adicione `.env` e `.token_cache.json` ao `.gitignore` (já configurado)
