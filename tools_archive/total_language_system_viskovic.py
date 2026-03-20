#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
from pathlib import Path

# ==============================================================================
# 1. KONFIGURACIJA
# ==============================================================================
BASE_DIR = Path('/var/www/fina-connect')
PROJECT_NAME = 'core'
LANGS = ['de', 'hr', 'en', 'tr', 'el']

print("🚀 POKRETANJE: Totalna Jezična Arhitektura (DE-HR-EN-TR-EL)")

def backup_and_write(path, content):
    if path.exists():
        shutil.copy2(path, str(path) + '.bak')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Integrirano: {path.name}")

# ==============================================================================
# 2. SETTINGS.PY - REKONSTRUKCIJA
# ==============================================================================
settings_path = BASE_DIR / PROJECT_NAME / 'settings.py'
with open(settings_path, 'r') as f:
    lines = f.readlines()

new_settings = []
skip = False
for line in lines:
    if any(x in line for x in ['LANGUAGE_CODE', 'USE_I18N', 'LANGUAGES =', 'LOCALE_PATHS', 'LANGUAGE_COOKIE']):
        continue
    if "'django.middleware.locale.LocaleMiddleware'" in line:
        continue
    new_settings.append(line)
    if "'django.contrib.sessions.middleware.SessionMiddleware'," in line:
        new_settings.append("    'django.middleware.locale.LocaleMiddleware',\n")

config_tail = f"""
# --- VISKOVIĆ GROUP MULTI-LANG ---
LANGUAGE_CODE = 'de'
USE_I18N = True
USE_L10N = True
USE_TZ = True
from django.utils.translation import gettext_lazy as _
LANGUAGES = [
    ('de', _('Deutsch')),
    ('hr', _('Hrvatski')),
    ('en', _('English')),
    ('tr', _('Türkçe')),
    ('el', _('Ελληνικά')),
]
LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 31536000
"""

backup_and_write(settings_path, "".join(new_settings) + config_tail)

# ==============================================================================
# 3. URLS.PY - ARHITEKTURA S PREFIKSIMA
# ==============================================================================
urls_path = BASE_DIR / PROJECT_NAME / 'urls.py'
urls_code = """from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static

# Osnovne rute (neovisne o jeziku)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
]

# Jezične rute s /de/, /hr/ prefiksima
urlpatterns += i18n_patterns(
    path('', include('appointments.urls')),
    path('premium/', include('premium_booking.urls')),
    path('partners/', include('partners.urls')),
    path('invoicing/', include('invoicing.urls')),
    prefix_default_language=True
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
"""
backup_and_write(urls_path, urls_code)

# ==============================================================================
# 4. STVARNI PRIJEVODI (DIZAJNIRANI ZA TVOJ WEB)
# ==============================================================================
translations = {
    'hr': {'Power': 'Snaga koja gradi budućnost.', 'Res': 'Ekskluzivni Resursi'},
    'de': {'Power': 'Kraft, die die Zukunft baut.', 'Res': 'Exklusive Ressourcen'},
    'en': {'Power': 'Power that builds the future.', 'Res': 'Exclusive Resources'},
    'tr': {'Power': 'Geleceği inşa eden güç.', 'Res': 'Özel Kaynaklar'},
    'el': {'Power': 'Η δύναμη που χτίζει το μέλλον.', 'Res': 'Αποκλειστικοί Πόροι'}
}

for lang in LANGS:
    po_dir = BASE_DIR / 'locale' / lang / 'LC_MESSAGES'
    po_dir.mkdir(parents=True, exist_ok=True)
    content = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
    for k, v in translations[lang].items():
        content += f'\nmsgid "{k}"\nmsgstr "{v}"\n'
    with open(po_dir / 'django.po', 'w', encoding='utf-8') as f:
        f.write(content)

# ==============================================================================
# 5. UI SWITCHER (INJEKCIJA U HEADER)
# ==============================================================================
switcher = """
    <div class="viskovic-lang-nav" style="display:flex; gap:12px; align-items:center; margin-left:30px; border-left:1px solid #252830; padding-left:20px;">
        {% get_current_language as CURRENT_LANG %}
        {% for lang in LANGUAGES %}
        <a href="/{{ lang.0 }}{{ request.get_full_path|slice:'3:' }}" 
           style="text-decoration:none; font-size:0.7rem; font-weight:700; color:{% if CURRENT_LANG == lang.0 %}#c9a84c{% else %}#555{% endif %}; text-transform:uppercase;">{{ lang.0 }}</a>
        {% if not forloop.last %}<span style="color:#252830; font-size:0.6rem;">/</span>{% endif %}
        {% endfor %}
    </div>
"""

idx_path = BASE_DIR / 'premium_booking/templates/premium_booking/index.html'
if idx_path.exists():
    with open(idx_path, 'r') as f:
        t_data = f.read()
    if '{% load i18n %}' not in t_data: t_data = '{% load i18n %}\n' + t_data
    t_data = t_data.replace('Ekskluzivni <span>Resursi</span>', '{% trans "Res" %}')
    if '</nav>' in t_data and 'viskovic-lang-nav' not in t_data:
        t_data = t_data.replace('</nav>', '</nav>' + switcher)
    with open(idx_path, 'w') as f: f.write(t_data)

# ==============================================================================
# 6. AKTIVACIJA
# ==============================================================================
print("🔄 Kompajliranje i restart...")
os.system(f"cd {BASE_DIR} && {BASE_DIR}/venv/bin/python manage.py compilemessages")
os.system(f"chown -R www-data:www-data {BASE_DIR}")
os.system("supervisorctl restart fina-connect")

print("\n" + "="*80)
print("✨ SUSTAV JE ONLINE. Provjeri: viskovic-group.de/de/premium/")
print("="*80)
