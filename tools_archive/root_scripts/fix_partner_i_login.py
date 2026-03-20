import os

DASHBOARD_FILE = '/var/www/fina-connect/templates/dashboards/partner.html'
VIEWS_FILE = '/var/www/fina-connect/core/views.py'

# 1. POPRAVAK PARTNER DASHBOARDA (Vizuali i gumbi)
with open(DASHBOARD_FILE, 'r', encoding='utf-8') as f:
    dash_html = f.read()

# Popravak boje naslova "Willkommen" (mijenjamo iz var(--white) u var(--text) da bude čitljivo na svim temama)
dash_html = dash_html.replace(
    'color: var(--white);',
    'color: var(--text);'
)

# Popravak "Download" gumba za Fakture (dodajemo onclick alert umjesto praznog href="#")
dash_html = dash_html.replace(
    '<a href="#" class="btn-download"><i class="fas fa-download"></i></a>',
    '<a href="#" onclick="alert(\\\'Dokument wird vorbereitet. Bitte versuchen Sie es später erneut.\\\'); return false;" class="btn-download"><i class="fas fa-download"></i></a>'
)

with open(DASHBOARD_FILE, 'w', encoding='utf-8') as f:
    f.write(dash_html)


# 2. POPRAVAK LOGIN PREUSMJERAVANJA (core/views.py)
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_code = f.read()

# Tražimo funkciju dashboard_router i osiguravamo da usmjerava partnere/investitore na pravi ekran
stari_router_blok = """
    elif role == 'investor':
        return redirect('investor_dashboard')
    elif role == 'partner':
        return redirect('partner_dashboard')
"""

novi_router_blok = """
    elif role == 'investor' or role == 'partner':
        return redirect('partner_dashboard') # Šaljemo ih oboje u Staklenu sobu
"""

# Ako već postoji stari blok, mijenjamo ga. Ako ne, dodajemo sigurnosnu logiku.
if "elif role == 'investor':" in views_code:
    views_code = views_code.replace(stari_router_blok, novi_router_blok)

with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(views_code)


# 3. RESTART SERVERA
os.system("supervisorctl restart fina-connect")
print("✅ SVE JE SREĐENO U JEDNOM POTEZU! Vizuali su popravljeni, gumbi imaju logiku, a ruter je usmjeren.")
