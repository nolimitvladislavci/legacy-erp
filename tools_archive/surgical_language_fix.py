#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

BASE_DIR = Path('/var/www/fina-connect')
SETTINGS = BASE_DIR / 'core/settings.py'
URLS = BASE_DIR / 'core/urls.py'

print("🛠️ KIRURŠKI ZAHVAT: Dodavanje TR i EL jezika na postojeći kod...")

# 1. VRAĆANJE ORIGINALNOG URLS.PY
if Path(str(URLS) + '.bak').exists():
    os.system('cp /var/www/fina-connect/core/urls.py.bak /var/www/fina-connect/core/urls.py')
    print("✅ Originalni urls.py je vraćen.")

# 2. SIGURNA MODIFIKACIJA TVOG SETTINGS.PY
with open(SETTINGS, 'r', encoding='utf-8') as f:
    content = f.read()

# Zamjena postojećeg LANGUAGES bloka s proširenim (strogo očuvana indentacija)
lang_pattern = re.compile(r'LANGUAGES\s*=\s*\[.*?\]', re.DOTALL)
new_langs = """LANGUAGES = [
    ('de', _('Deutsch')),
    ('hr', _('Hrvatski')),
    ('en', _('English')),
    ('tr', _('Türkçe')),
    ('el', _('Ελληνικά')),
]

# FORSIRANJE KORISNIČKOG ODABIRA NAD POSTAVKAMA MOBITELA
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 31536000"""

if "'Türkçe'" not in content:
    content = lang_pattern.sub(new_langs, content)

# Postavljanje DE kao default
content = re.sub(r"LANGUAGE_CODE\s*=\s*['\"]hr['\"]", "LANGUAGE_CODE = 'de'", content)

with open(SETTINGS, 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ Settings.py je sigurno ažuriran (5 jezika).")

# 3. SIGURNA MODIFIKACIJA TVOG URLS.PY (Samo dodavanje i18n rute)
with open(URLS, 'r', encoding='utf-8') as f:
    urls_content = f.read()

if "path('i18n/', include('django.conf.urls.i18n'))" not in urls_content:
    urls_content = urls_content.replace(
        "urlpatterns = [",
        "urlpatterns = [\n    path('i18n/', include('django.conf.urls.i18n')),\n"
    )
    with open(URLS, 'w', encoding='utf-8') as f:
        f.write(urls_content)
    print("✅ i18n ruta dodana u urls.py.")

