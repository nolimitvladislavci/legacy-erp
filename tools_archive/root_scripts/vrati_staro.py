import os

BASE_DIR = '/var/www/fina-connect'
WEBSITE_DIR = os.path.join(BASE_DIR, 'website')

# 1. Vraćamo views.py da ponovno učitava vaš STARI viskovic_group_index.html za naslovnicu
with open(os.path.join(WEBSITE_DIR, 'views.py'), 'r', encoding='utf-8') as f:
    views_content = f.read()

# Prepisujemo homepage view nazad
views_content = views_content.replace(
    'return render(request, "website/homepage.html")',
    'return render(request, "viskovic_group_index.html")'
)

with open(os.path.join(WEBSITE_DIR, 'views.py'), 'w', encoding='utf-8') as f:
    f.write(views_content)

# 2. Popravljamo glavni core/urls.py da direktno prepoznaje i /bau i stari website
URLS_FILE = os.path.join(BASE_DIR, 'core', 'urls.py')
with open(URLS_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

if "path('bau/'," not in content:
    content = content.replace(
        "path('website/', include('website.urls')),",
        "path('bau/', __import__('website.views', fromlist=['bau_page']).bau_page, name='bau_page_root'),\n    path('website/', include('website.urls')),"
    )
    with open(URLS_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

os.system("supervisorctl restart fina-connect")
print("✅ USPJEH! Stara naslovnica je vraćena. Nova /bau/ ruta je aktivna.")
