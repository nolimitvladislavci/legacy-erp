#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

BASE_DIR = Path('/var/www/fina-connect')

print("🔍 Tražim datoteku javne naslovnice...")

switcher_html = """
        <div style="display:inline-flex; gap:10px; align-items:center; margin:0 15px; border-left:1px solid #252830; border-right:1px solid #252830; padding:0 20px;">
            <form action="/i18n/setlang/" method="post" style="margin:0; display:flex; gap:10px;">
                {% csrf_token %}
                <input name="next" type="hidden" value="{{ request.get_full_path }}">
                {% get_current_language as CURRENT_LANG %}
                {% for lang in LANGUAGES %}
                    <button type="submit" name="language" value="{{ lang.0 }}" 
                    style="background:none; border:none; padding:0; cursor:pointer; font-family:'Barlow', sans-serif; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:2px; transition:0.3s; color:{% if CURRENT_LANG == lang.0 %}#c9a84c{% else %}#9aa0b0{% endif %};">
                    {{ lang.0 }}
                    </button>
                {% endfor %}
            </form>
        </div>
        """

found = False

for root, dirs, files in os.walk(BASE_DIR):
    if 'venv' in root or 'static' in root or '.git' in root:
        continue
        
    for file in files:
        if file.endswith('.html'):
            file_path = Path(root) / file
            try:
                content = file_path.read_text(encoding='utf-8')
                
                # Prepoznajemo datoteku po specifičnoj klasi koju si poslao
                if 'class="nav-erp">ERP Portal' in content:
                    print(f"📍 Pronađena javna naslovnica: {file_path}")
                    found = True
                    
                    if 'VISKOVIC JAVNI LANG SWITCHER' not in content:
                        # 1. Učitavanje i18n na vrh
                        if '{% load i18n %}' not in content:
                            content = '{% load i18n %}\n' + content
                        
                        # 2. Umetanje izbornika neposredno prije ERP Portal gumba
                        content = content.replace(
                            '<a href="https://limit-connect.com/login/" class="nav-erp">', 
                            switcher_html + '\n        <a href="https://limit-connect.com/login/" class="nav-erp">'
                        )
                        
                        file_path.write_text(content, encoding='utf-8')
                        print("✅ Jezični izbornik je uspješno integriran u navigaciju.")
                    else:
                        print("ℹ️ Izbornik se već nalazi u ovoj datoteci.")
            except Exception as e:
                pass

if found:
    print("🔄 Restartam server...")
    os.system(f"chown -R www-data:www-data {BASE_DIR}")
    os.system("supervisorctl restart fina-connect")
    print("✨ GOTOVO! Osvježi svoju crnu naslovnicu (viskovic-group.de).")
else:
    print("❌ Datoteka s klasom 'nav-erp' nije pronađena.")
