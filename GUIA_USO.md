# 🎯 Guia de Uso — Teams Mention Detector

## Como a detecção funciona agora

A aplicação foi melhorada para capturar menções no Teams de **4 maneiras diferentes**:

### 1. **Menção com @ + Nome Completo**
```
Oi @Vinicius Campos, tudo bem?  ✅ Detecta
```

### 2. **Menção com @ + Primeiro Nome**
```
Oi @Vinicius, veja isso.        ✅ Detecta
```

### 3. **Pílula de menção sem @ (Teams renderiza assim)**
```
Oi Vinicius Campos, como vai?   ✅ Detecta
Vinicius, você viu?              ✅ Detecta
```

### 4. **Nome com contexto (sem @ explícito)**
```
Reunião com Vinicius amanhã      ✅ Detecta
Vinicius é incrível              ✅ Detecta
```

## Como usar

### Modo 1: Teste Rápido (recomendado para verificar funcionamento)
```bash
# Faz uma verificação manual AGORA
python main.py --check-now
```

### Modo 2: Telegram de teste
```bash
# Envia uma mensagem de teste ao Telegram para verificar integração
python main.py --test-tg
```

### Modo 3: Scheduler contínuo (monitoramento 24/7)
```bash
# Roda indefinidamente, verificando a cada N minutos
python main.py
```

## Configuração do .env

Seu `.env` já está correto:

```bash
MENTION_TARGETS=Vinicius Campos   # Nome a monitorar
MONITOR_START_TIME=08:00          # Início do monitoramento
MONITOR_END_TIME=23:00            # Fim do monitoramento
CHECK_INTERVAL_MINUTES=1          # Verifica a cada 1 minuto
```

### Para adicionar mais nomes:
```bash
MENTION_TARGETS=Vinicius Campos,Jose Silva,Maria Santos
```

## Fluxo de detecção

```
1. Browser abre Teams Web → Extrai mensagens de hoje
2. JavaScript procura por elementos de @menção (pílulas, spans especiais)
3. Se encontra pilha: extrai conteúdo + remetente + timestamp
4. Fallback: se JS não achar, busca texto e procura @nome ou nome
5. Se menção encontrada → envia notificação via Telegram
6. Deduplicação: não envia a mesma menção 2x
```

## O que foi corrigido

### ❌ Problema Antigo
- Procurava apenas por `@vinicius campos` (nome completo)
- Não detectava `@vinicius` (só primeiro nome)
- Não funcionava quando Teams renderizava pílulas sem @ no texto

### ✅ Solução Implementada

**JavaScript melhorado:**
- Procura por elementos com classe `mention`, `pill`, `atMention`, etc
- Detecta estilos especiais (background colorido das pílulas)
- Extrai remetente e conteúdo completo da mensagem

**Detecção de nome melhorada:**
- Agora busca por nome completo OU primeiro nome
- Funciona com ou sem @ no texto
- Detecta variações (Vinicius, vinicius, VINICIUS, etc)
- Procura contexto para evitar falsos positivos

**Fallback robusto:**
- Se elementos de menção não forem encontrados no DOM
- Procura pelo nome no texto extraído
- Verifica se há contexto real (não é isolado)

## Testes

Para verificar que a detecção está funcionando:

```bash
# Testa vários formatos de menção
python test_mention_detection.py
```

Resultado esperado: **11/11 testes passarem ✅**

## Próximos passos

1. Execute `python main.py --check-now` para testar agora
2. Se encontrar menções de hoje, vai enviá-las ao Telegram
3. Se não encontrar, significa que não há menções ou Teams ainda não carregou
4. Depois rode `python main.py` para monitoramento contínuo

## Troubleshooting

### "Nenhuma menção encontrada"
- Certifique-se de que há menções de **hoje** no Teams
- Verifique que `MENTION_TARGETS` está correto (sensível a espaços)
- Rode `python main.py --check-now` para debug

### "Mensagens duplicadas no Telegram"
- Isso não deve acontecer — há deduplicação por hash
- Se ocorrer, tente deletar `notified.json`

### Telegram não funciona
```bash
# Verifica se o bot está acessível
python main.py --test-tg

# Se falhar, verifique o token:
python main.py --get-chat-id
```

---

**Pronto para usar!** 🚀 Rode `python main.py` e comece a receber notificações.
