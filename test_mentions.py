import re
target = 'Vinicius Campos'
parts = target.split()
first_name = parts[0]
if len(parts) > 1:
    target_re = rf'({re.escape(target)}|{re.escape(first_name)})'
else:
    target_re = re.escape(target)

pattern = re.compile(rf'@{target_re}\b', re.IGNORECASE)

sents = [
    'Oi @Vinicius Campos, tudo bem?',
    'Oi @Vinicius, veja isso.',
    'Fala @Jose, tranquilo?',
    'Alou @Maria, bom dia',
    'Reunião com @ViniciusCampos',
    'E aí @vinicius, blz?'
]

for s in sents:
    print(f'{s} -> {bool(pattern.search(s))}')
