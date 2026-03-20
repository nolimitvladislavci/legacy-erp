#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

BASE_DIR = Path('/var/www/fina-connect')

print("🔍 POKRETANJE GLOBALNE INJEKCIJE: Skeniranje cijelog web sadržaja...")

# Globalni jezični izbornik (Zlatni Visković dizajn, responzivan)
switcher_html = """
    <div style="display:inline-flex; gap:10px; align-items:center; margin-left:auto; padding:0 20px; z-index:9999;">
        <form action="/i18n/setlang/" method="post" style="margin:0; display:flex; gap:10px;">
            {% csrf_token %}
            <input name="next" type="hidden" value="{{ request.get_full_path }}">
            {% get_current_language as CURRENT_LANG %}
            {% for lang in LANGUAGES %}
                <button type="submit" name="language" value="{{ lang.0 }}" 
                style="background:none; border:none; padding:0; cursor:pointer; font-family:'Barlow', sans-serif; font-size:14px; font-weight:bold; text-transform:uppercase; transition:0.3s; color:{% if CURRENT_LANG == lang.0 %}#c9a84c{% else %}#888{% endif %};">
                {{ lang.0 }}
                </button>
            {% endfor %}
        </form>
    </div>
"""

modified_files = 0

# Prolazak kroz sve mape i podmape tvog projekta
for root, dirs, files in os.walk(BASE_DIR):
    # Preskačemo virtualno okruženje i statične datoteke kako ne bismo dirali tuđi kod
    if 'venv' in root or 'site-packages' in root or 'static' in root or '.git' in root:
        continue
        
    for file in files:
        if file.endswith('.html'):
            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Uvjet: Datoteka mora imati header ili nav, i ne smije već imati naš switcher
                if ('</header>' in content or '</nav>' in content) and 'VISKOVIC GLOBAL LANG SWITCHER' not in content:
                    
                    # 1. Osiguravamo učitavanje i18n tagova
                    if '{% load i18n %}' not in content:
                        content = '{% load i18n %}\n' + content

                    # 2. Injekcija izbornika neposredno prije zatvaranja navigacije ili headera
                    if '</nav>' in content:
                        content = content.replace('</nav>', switcher_html + '\n</nav>')
                    elif '</header>' in content:
                        content = content.replace('</header>', switcher_html + '\n</header>')
                    
                    # Spremanje promjena
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"✅ Izbornik dodan u: {file_path.parent.name}/{file_path.name}")
                    modified_files += 1
            except Exception as e:
                print(f"⚠️ Preskočeno {file.name}: {e}")

print(f"\n✨ ZAVRŠENO! Ukupno nadograđeno predložaka: {modified_files}")

# Restart servisa kako bi promjene bile odmah vidljive
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("supervisorctl restart fina-connect")
print("🚀 Server je restartan. Provjeri bilo koju stranicu na portalu.")
