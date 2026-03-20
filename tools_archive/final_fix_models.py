path = '/var/www/fina-connect/invoicing/fiscal_models.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_until_meta = False

for line in lines:
    # Kada pronađemo klasu FiscalConfig, resetiramo njezina polja
    if "class FiscalConfig(models.Model):" in line:
        new_lines.append(line)
        new_lines.append("    cert_path = models.CharField(max_length=255, blank=True, null=True, default='/var/www/fina-connect/certs/fina_cert.p12')\n")
        new_lines.append("    cert_file = models.FileField(upload_to='certs/', null=True, blank=True, help_text='Učitajte .p12 certifikat direktno')\n")
        new_lines.append("    use_production = models.BooleanField(default=False)\n")
        new_lines.append("    invoice_prefix_hr = models.CharField(max_length=10, default='KNJ')\n")
        new_lines.append("    next_invoice_number = models.IntegerField(default=1)\n")
        skip_until_meta = True
        continue
    
    # Preskačemo stare, neispravne linije dok ne dođemo do Meta klase ili metoda
    if skip_until_meta:
        if "class Meta:" in line or "def " in line or "@classmethod" in line:
            skip_until_meta = False
            new_lines.append(line)
        continue
    
    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("✓ FiscalConfig klasa je uspješno rekonstruirana s ispravnom indentacijom.")
