path = '/var/www/fina-connect/invoicing/fiscal_models.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Popravljamo odrezani cert_path i dodajemo cert_file s ispravnom indentacijom
    if "cert_path = models.CharField(max_length=255," in line:
        new_lines.append("    cert_path = models.CharField(max_length=255, blank=True, null=True)\n")
        new_lines.append("    cert_file = models.FileField(upload_to='certs/', null=True, blank=True, help_text='Učitajte .p12 certifikat direktno')\n")
    elif "cert_file =" in line:
        # Preskačemo duplikate koje je sed možda napravio
        continue
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
