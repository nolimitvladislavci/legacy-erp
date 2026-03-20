path = '/var/www/fina-connect/invoicing/fiscalization.py'
with open(path) as f:
    content = f.read()

old = "logger.info(f\"ZKI generiran za račun {invoice.number}: {zki[:8]}...\")"
new = "logger.info(f\"ZKI generiran za račun {getattr(invoice, 'number', '?')}: {zki[:8]}...\")"

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('OK: fiscalization.py fixed - number now uses getattr')
else:
    print('ERROR: pattern not found')
    idx = content.find('logger.info')
    print(repr(content[idx:idx+120]))
