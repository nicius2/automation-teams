# 🔧 Correções de Mensagens Antigas e Duplicadas

## Problemas Resolvidos

### 1. **Mensagens Antigas Sendo Notificadas**
❌ **Antes:** Sistema pegava mensagens de dias anteriores
✅ **Depois:** Filtro rigoroso para garantir "de hoje"

**Melhorias no JavaScript (`teams_client.py` linhas 496-639):**
- Usa **horário local** (não UTC) para calcular data de hoje
- Verificação dupla:
  1. Se tem atributo `datetime` (ISO format): verifica se começa com YYYY-MM-DD de hoje
  2. Se não tem: usa regex `/^\d{1,2}:\d{2}/` - hoje mostra HH:MM, antigo mostra data completa
- Aplica filtro em AMBAS as estratégias (menções estruturadas + fallback)

**Exemplo:**
```
Hoje na tela do Teams: "14:30"      ✅ Detecta como de hoje
Antigo na tela:        "12 de mar"  ❌ Rejeita como antigo
```

### 2. **Notificações Duplicadas no Telegram**
❌ **Antes:** Mesmo arquivo com mesma mensagem era notificado 2-3x
✅ **Depois:** Deduplicação robusta por remetente + conteúdo

**Melhorias no Hash (`scheduler.py` linhas 60-78):**
- Inclui: `canal::remetente::conteúdo`
- Normaliza conteúdo (remove espaços extras, quebras de linha)
- Mesmo conteúdo do mesmo remetente = mesmo hash
- JavaScript também deduplica antes de retornar (linha 653-660)

**Exemplo:**
```
Mensagem 1: "João Silva :: Oi, tudo bem?"
Mensagem 2: "João Silva :: Oi,  tudo  bem?" (espaços extras)
Mensagem 3: "João Silva :: Oi,\ntudo bem?" (quebra de linha)

Resultado: ✅ Todas geram o MESMO hash → notificada 1x apenas
```

---

## Como Usar Agora

### Teste imediato (mais rápido)
```bash
python main.py --check-now
```
Verifica menções de **HOJE APENAS** e notifica novas.

### Monitoramento contínuo (a cada 30s)
```bash
python main.py
```
Rodará indefinidamente, checando a cada 30 segundos.

### Se receber notificações antigas (debug)
```bash
python main.py --clear-cache
```
💡 Limpa o histórico de notificadas, mas próxima execução só notifica **de hoje**.

---

## Detalhes Técnicos

### Filtro de Data no JavaScript
```javascript
// Calcula data de hoje em horário LOCAL (não UTC)
const today = new Date();
const todayDate = today.getFullYear() + '-' +
                  String(today.getMonth() + 1).padStart(2, '0') + '-' +
                  String(today.getDate()).padStart(2, '0');

// Verifica rigorosamente:
if (dtAttr.startsWith(todayDate))  // ← Timestamp ISO
    isToday = true;
else if (/^\d{1,2}:\d{2}/.test(timeText))  // ← Hora (HH:MM)
    isToday = true;
```

### Hash Normalizado
```python
# Antes: "canal::conteúdo"
# Depois: "canal::remetente::conteúdo"

# Normalized (remove variações de renderização):
raw = f"{channel}::{sender}::{content}"
hash = md5(raw).hexdigest()[:16]
```

---

## Log de Debug

Se quiser ver exatamente o que está acontecendo:

```bash
# Mostra se mensagen é de hoje:
python main.py --check-now

# Output esperado:
⏰ 12/03 16:05 — Verificando menções...
  🔎 Validando sessão...
  ✅ Sessão válida!
🔍 Verificando menções no Teams Web...
  ⏳ Aguardando Teams carregar...
  ✅ Teams carregado em: https://teams.live.com/v2/
  💬 3 chat(s) encontrado(s)
  📂 Verificando: [nome do chat]
  🎯 5 @menção(ões) HOJE em '[chat]'  ← Apenas de HOJE!
✅ 2 nova(s) notificação(ões) enviada(s)
   (3 duplicata(s) não enviada(s))      ← Deduplicadas!
```

---

## Garantias Agora

✅ **Só notifica mensagens de hoje** (data local, não UTC)
✅ **Não envia mensagens antigas** (verificação dupla no DOM)
✅ **Não envia duplicatas** (hash por remetente + conteúdo)
✅ **Normaliza espaços/quebras de linha** (renderização robusta)

Está pronto! 🎉
