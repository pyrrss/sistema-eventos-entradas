import re

with open('/home/sephir/sistema-eventos-entradas/frontend/js/ui.js', 'r') as f:
    content = f.read()

# HTML entities - Python string literals must contain the entity strings
esc_func = "export function esc(value) {\n  return String(value ?? '')\n    .replaceAll('&', '&')\n    .replaceAll('<', '<')\n    .replaceAll('>', '>')\n    .replaceAll('\"', '"')\n    .replaceAll(\"'\", ''');\n}"

new_content = re.sub(
    r'export function esc\(value\) \{[\s\S]*?^\}',
    esc_func,
    content,
    flags=re.MULTILINE
)

with open('/home/sephir/sistema-eventos-entradas/frontend/js/ui.js', 'w') as f:
    f.write(new_content)

print('Fixed')