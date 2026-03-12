#!/usr/bin/env python3
"""
Script para testar a detecção de menções com vários formatos.
Simula como o Teams renderiza menções.
"""
import re
from teams_monitor.config import MENTION_TARGETS

def test_is_mentioned(text: str) -> bool:
    """Testa a função _is_mentioned() com diferentes formatos."""
    for target in MENTION_TARGETS:
        parts = target.split()
        first_name = parts[0]

        # 1. Tenta com @ — nome completo
        if re.search(rf'@\s*{re.escape(target)}\b', text, re.IGNORECASE):
            return True

        # 2. Tenta com @ — apenas primeiro nome
        if re.search(rf'@\s*{re.escape(first_name)}\b', text, re.IGNORECASE):
            return True

        # 3. Tenta sem @ — nome completo (Teams renderiza pílulas sem o @ no texto)
        match = re.search(rf'\b{re.escape(target)}\b', text, re.IGNORECASE)
        if match:
            start, end = match.span()
            has_context = (start > 0 and end < len(text))
            if has_context:
                return True

        # 4. Tenta sem @ — apenas primeiro nome com contexto
        match = re.search(rf'\b{re.escape(first_name)}\b', text, re.IGNORECASE)
        if match:
            start, end = match.span()
            # Precisa de contexto: pode ter 2+ caracteres antes ou depois
            has_context = (start >= 2 or end + 2 < len(text))
            if has_context:
                return True

    return False


def run_tests():
    """Executa testes de detecção."""
    print(f"📝 MENTION_TARGETS configurado: {MENTION_TARGETS}\n")

    test_cases = [
        # Formatos com @
        ("Oi @Vinicius Campos, tudo bem?", True, "Menção completa com @"),
        ("Oi @Vinicius, veja isso.", True, "Menção só primeiro nome com @"),
        ("@vinicius campos pode vir aqui?", True, "Lowercase com @"),

        # Formatos SEM @ (Teams renderiza pílulas assim)
        ("Oi Vinicius Campos, como vai?", True, "Nome completo sem @ (pílula)"),
        ("Vinicius, você viu?", True, "Só primeiro nome sem @ (pílula)"),
        ("Reunião com VINICIUS CAMPOS amanhã", True, "Uppercase sem @"),

        # Casos onde NÃO deve detectar
        ("Conversa com José", False, "Nome diferente"),

        # Cases onde deve detectar (contexto)
        ("Vinicius é o nome dele", True, "Nome como contexto"),
        ("Meu vizinho Vinicius", True, "Nome sozinho com contexto"),
        ("@vinicius @ campos", True, "Tem @vinicius (menção real)"),
        ("Vinicius123", False, "Nome sem espaço/word boundary"),
    ]

    print("🧪 Testando detecção de menções:\n")
    passed = 0
    failed = 0

    for text, expected, description in test_cases:
        result = test_is_mentioned(text)
        status = "✅" if result == expected else "❌"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {description}")
        print(f"   Texto: \"{text}\"")
        print(f"   Esperado: {expected}, Obtido: {result}\n")

    print(f"\n📊 Resultado: {passed} passaram, {failed} falharam")
    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
