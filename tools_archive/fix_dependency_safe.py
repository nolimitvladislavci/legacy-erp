import os
import sys

# Putanja do datoteke koja vrišti grešku
file_path = '/var/www/fina-connect/accounts/migrations/0002_alter_userprofile_options_and_more.py'

if not os.path.exists(file_path):
    print(f"GREŠKA: Ne mogu naći datoteku: {file_path}")
    sys.exit(1)

# Čitanje datoteke
with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
found = False

# Tražimo liniju s ovisnosti o staroj companies aplikaciji
for line in lines:
    if "('companies', '0001_initial')" in line:
        # Ovo je problematična linija - preskačemo je (brišemo)
        print(f"Uklanjam ovisnost: {line.strip()}")
        found = True
        continue
    new_lines.append(line)

# Spremanje popravljene datoteke
if found:
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    print("USPJEH: Ovisnost je sigurno uklonjena.")
else:
    print("INFO: Problematična ovisnost nije pronađena (možda je već obrisana?).")

