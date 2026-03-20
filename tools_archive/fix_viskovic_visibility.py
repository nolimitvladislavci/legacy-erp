#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

BASE_HTML = Path('/var/www/fina-connect/templates/base.html')
URLS_PY = Path('/var/www/fina-connect/core/urls.py')

print("🛠️ KIRURŠKI ZAHVAT: Otkrivanje skrivenog izbornika i mapiranje rute...")

# 1. POPRAVAK CSS-a U BASE.HTML (Prikaz na mobitelima)
html_content = BASE_HTML.read_text(encoding='utf-8')
# Mijenjamo display:none u display:flex kako bi gumbi bili vidljivi i na malim ekranima
new_html = re.sub(
    r'\.lang-switcher\s*\{\s*display:\s*none;\s*\}', 
    '.lang-switcher { display: flex; gap: 3px; transform: scale(0.9); }', 
    html_content
)
if html_content != new_html:
    BASE_HTML.write_text(new_html, encoding='utf-8')
    print("✅ CSS ažuriran: Jezični izbornik je sada vidljiv i na mobitelima.")

# 2. POPRAVAK URLS.PY (Premještanje premium rute pod jezike)
urls_content = URLS_PY.read_text(encoding='utf-8')
# Prvo sigurno brišemo premium rutu iz gornjeg (običnog) bloka
new_urls = re.sub(r"^[ \t]*path\('premium/', include\('premium_booking\.urls'\)\),?\n?", "", urls_content, flags=re.MULTILINE)
# Zatim je dodajemo u i18n_patterns (prevedeni) blok
new_urls = re.sub(
    r'(urlpatterns \+= i18n_patterns\()', 
    r"\1\n    path('premium/', include('premium_booking.urls')),", 
    new_urls
)

if urls_content != new_urls:
    URLS_PY.write_text(new_urls, encoding='utf-8')
    print("✅ Rute ažurirane: Premium modul sada podržava /de/, /hr/ prefikse.")

# 3. RESTART SERVERA
print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")
print("✨ ZAVRŠENO! Osvježi stranicu na mobitelu i računalu.")
