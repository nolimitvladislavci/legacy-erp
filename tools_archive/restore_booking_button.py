#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

TARGET_FILES = [
    Path('/var/www/fina-connect/website/templates/website/homepage.html'),
    Path('/var/www/fina-connect/templates/viskovic_group_index.html')
]

print("🛠️ Vraćanje gumba 'REZERVIRAJ TERMIN' na naslovnicu...")

for file_path in TARGET_FILES:
    if file_path.exists():
        content = file_path.read_text(encoding='utf-8')
        
        # Provjera je li gumb slučajno već tu
        if 'href="/appointments/booking/"' not in content:
            # Tražimo div hero-actions i gumb Naši brendovi
            pattern = r'(<div class="hero-actions">\s*)(<a href="#brendovi" class="btn-primary">Naši brendovi</a>)'
            
            # Ubacujemo bijeli gumb za rezervacije ispred gumba za brendove
            replacement = r'\1<a href="/appointments/booking/" class="btn-primary" style="background: var(--white); color: var(--black);">Rezerviraj termin</a>\n        \2'
            
            new_content = re.sub(pattern, replacement, content)
            
            if new_content != content:
                file_path.write_text(new_content, encoding='utf-8')
                print(f"✅ Gumb vraćen u: {file_path.name}")
            else:
                print(f"⚠️ Nisam uspio pronaći točno mjesto za ubacivanje u {file_path.name}")
        else:
            print(f"ℹ️ Gumb 'Rezerviraj termin' već postoji u {file_path.name}")

print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")
print("✨ GOTOVO! Osvježi svoju crnu naslovnicu.")
