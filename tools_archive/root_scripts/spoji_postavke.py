import os

BASE_DIR = '/var/www/fina-connect'
SETTINGS_FILE = os.path.join(BASE_DIR, 'core', 'settings.py')
CP_FILE = os.path.join(BASE_DIR, 'website', 'context_processors.py')
BAU_FILE = os.path.join(BASE_DIR, 'website', 'templates', 'website', 'bau.html')

# 1. Kreiramo Context Processor
cp_content = """from .models import SiteSettings

def global_settings(request):
    # Povlači prve postavke koje ste kreirali u adminu
    settings = SiteSettings.objects.first()
    return {'site_settings': settings}
"""
with open(CP_FILE, 'w', encoding='utf-8') as f:
    f.write(cp_content)

# 2. Ubacujemo Context Processor u glavne postavke (core/settings.py)
with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
    settings_code = f.read()

if "'website.context_processors.global_settings'" not in settings_code:
    settings_code = settings_code.replace(
        "'django.template.context_processors.request',",
        "'django.template.context_processors.request',\n                'website.context_processors.global_settings',"
    )
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        f.write(settings_code)

# 3. Dinamički povezujemo podatke na bau.html
with open(BAU_FILE, 'r', encoding='utf-8') as f:
    bau_html = f.read()

# Zamjena za godinu osnivanja (u Stats Bar-u)
bau_html = bau_html.replace(
    '<div class="stat-num">20+</div>\n        <div class="stat-label">Jahre Erfahrung</div>',
    '<div class="stat-num">Seit {{ site_settings.founded_year|default:"2018" }}</div>\n        <div class="stat-label">In Deutschland</div>'
)

# Zamjena za gumb u zaglavlju (Header)
bau_html = bau_html.replace(
    'href="#kontakt" class="btn-primary" style="padding: 10px 20px; font-size: 0.75rem;">Kontakt',
    'href="tel:{{ site_settings.phone_1_number|default:\'+4915234209056\' }}" class="btn-primary" style="padding: 10px 20px; font-size: 0.75rem;">📞 {{ site_settings.phone_1_number|default:"Kontakt" }}'
)

# Zamjena za veliki broj u CTA sekciji
bau_html = bau_html.replace(
    '<a href="tel:+4915234209056" class="btn-primary" style="font-size: 1.2rem; width: 100%; max-width: 400px; padding: 20px;">📞 015 234 209 056</a>',
    '<a href="tel:{{ site_settings.phone_1_number|default:\'+4915234209056\' }}" class="btn-primary" style="font-size: 1.2rem; width: 100%; max-width: 400px; padding: 20px;">📞 {{ site_settings.phone_1_number|default:\'015 234 209 056\' }}</a>'
)

# Zamjena za email u CTA sekciji
bau_html = bau_html.replace(
    '<a href="mailto:viskovic.bau@gmail.com" style="color: var(--gold); text-decoration: none; font-size: 1.1rem; margin-top: 10px; border-bottom: 1px solid var(--gold); padding-bottom: 4px;">viskovic.bau@gmail.com</a>',
    '<a href="mailto:{{ site_settings.email|default:\'viskovic.bau@gmail.com\' }}" style="color: var(--gold); text-decoration: none; font-size: 1.1rem; margin-top: 10px; border-bottom: 1px solid var(--gold); padding-bottom: 4px;">{{ site_settings.email|default:\'viskovic.bau@gmail.com\' }}</a>'
)

# Zamjena za Footer (Copyright i Naziv Tvrtke)
bau_html = bau_html.replace(
    '<div class="footer-copy">© 2026 Visković Group · Ein Unternehmen der Visković Group</div>',
    '<div class="footer-copy">© {% now "Y" %} {{ site_settings.company_name|default:"Visković Group" }} · Ein Unternehmen der Visković Group</div>'
)

with open(BAU_FILE, 'w', encoding='utf-8') as f:
    f.write(bau_html)

# 4. Restart servera
os.system("supervisorctl restart fina-connect")
print("✅ USPJEH! Podaci iz Admin Panela su sada dinamički povezani sa javnom web stranicom.")
