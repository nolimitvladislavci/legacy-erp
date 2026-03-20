#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

# Točne putanje koje smo dobili iz grep naredbe
TARGET_FILES = [
    Path('/var/www/fina-connect/website/templates/website/homepage.html'),
    Path('/var/www/fina-connect/templates/viskovic_group_index.html')
]

print("🛠️ KIRURŠKI ZAHVAT: Integracija jezika u javnu naslovnicu...")

# Visković Group dizajn za javnu navigaciju (zlatna i bijela slova)
switcher_html = """
        <div class="lang-switcher" style="display:inline-flex; gap:12px; align-items:center; margin-left:30px; border-left:1px solid #252830; padding-left:20px;">
            <form action="/i18n/setlang/" method="post" style="margin:0; display:flex; gap:12px;">
                {% csrf_token %}
                <input name="next" type="hidden" value="{{ request.get_full_path }}">
                {% get_current_language as CURRENT_LANG %}
                {% for lang in LANGUAGES %}
                    <button type="submit" name="language" value="{{ lang.0 }}" 
                    style="background:none; border:none; padding:0; cursor:pointer; font-family:'Barlow', sans-serif; font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:1px; transition:0.3s; color:{% if CURRENT_LANG == lang.0 %}#c9a84c{% else %}#f0ede8{% endif %};">
                    {{ lang.0 }}
                    </button>
                {% endfor %}
            </form>
        </div>
"""

for file_path in TARGET_FILES:
    if file_path.exists():
        content = file_path.read_text(encoding='utf-8')
        
        if 'VISKOVIC JAVNI LANG SWITCHER' not in content:
            # Učitavanje i18n taga na sam vrh datoteke
            if '{% load i18n %}' not in content:
                content = '{% load i18n %}\n' + content
            
            # Sigurno umetanje izbornika neposredno prije zatvaranja navigacije
            if '</nav>' in content:
                content = content.replace('</nav>', switcher_html + '\n</nav>')
                file_path.write_text(content, encoding='utf-8')
                print(f"✅ Uspješno integrirano u: {file_path.name}")
            else:
                print(f"⚠️ Nije pronađen <nav> tag u {file_path.name}")
        else:
            print(f"ℹ️ Izbornik već postoji u {file_path.name}")

print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")
print("✨ ZAVRŠENO! Osvježi svoju crnu naslovnicu (viskovic-group.de).")
