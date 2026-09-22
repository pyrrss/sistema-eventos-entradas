# Read as bytes
with open('/home/sephir/sistema-eventos-entradas/frontend/js/ui.js', 'rb') as f:
    content = f.read()

# New esc function as bytes - build programmatically to avoid quote issues
lines = [
    b"export function esc(value) {",
    b"  return String(value ?? '')",
    b"    .replaceAll('&', '&')",
    b"    .replaceAll('<', '<')",
    b"    .replaceAll('>', '>')",
    b"    .replaceAll('\"', '\"')",
    b"    .replaceAll(\"'\", ''');",
    b"}"
]
new_esc = b'\n'.join(lines)

# Find and replace
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