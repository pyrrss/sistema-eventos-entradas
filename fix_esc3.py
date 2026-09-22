with open('/home/sephir/sistema-eventos-entradas/frontend/js/ui.js', 'rb') as f:
    content = f.read()

# Build entity strings using chr() to avoid HTML entity interpretation
amp = chr(38) + chr(97) + chr(109) + chr(112) + chr(59)  # &
lt = chr(38) + chr(108) + chr(116) + chr(59)  # <
gt = chr(38) + chr(103) + chr(116) + chr(59)  # >
quot = chr(38) + chr(113) + chr(117) + chr(111) + chr(116) + chr(59)  # "
apos = chr(38) + chr(35) + chr(51) + chr(57) + chr(59)  # '

lines = [
    "export function esc(value) {",
    "  return String(value ?? '')",
    "    .replaceAll('&', '" + amp + "')",
    "    .replaceAll('<', '" + lt + "')",
    "    .replaceAll('>', '" + gt + "')",
    '    .replaceAll("\\"", "' + quot + '")',
    "    .replaceAll(\"'\", '" + apos + "');",
    "}"
]
new_esc = '\n'.join(lines).encode('utf-8')

start = content.find(b'export function esc(value) {')
if start == -1:
    print("NOT FOUND")
else:
    end = content.find(b'\n}', start)
    if end == -1:
        print("NO END FOUND")
    else:
        end += 2
        new_content = content[:start] + new_esc + content[end:]
        with open('/home/sephir/sistema-eventos-entradas/frontend/js/ui.js', 'wb') as f:
            f.write(new_content)
        print("Fixed!")