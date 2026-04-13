"""
╔══════════════════════════════════════════════════════════════════════════╗
║  FENIX SHELL TEST SUITE — v1.0 (09.04.2026)                            ║
║  Testira sve scenarije Shell Faze 1, 2 i 3                             ║
║                                                                          ║
║  Pokretanje:                                                             ║
║    venv/bin/python test_shell_suite.py                                  ║
║  Verbose:                                                                ║
║    venv/bin/python test_shell_suite.py -v                               ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from django.template.loader import get_template
from django.test import Client

# ─────────────────────────────────────────────────────────────────────────
# BOJE ZA OUTPUT
# ─────────────────────────────────────────────────────────────────────────
GRN = '\033[92m'
RED = '\033[91m'
YLW = '\033[93m'
BLU = '\033[94m'
GLD = '\033[93m'
RST = '\033[0m'
BLD = '\033[1m'

def ok(msg):  print(f"  {GRN}✅{RST} {msg}")
def fail(msg): print(f"  {RED}❌{RST} {msg}")
def warn(msg): print(f"  {YLW}⚠️ {RST} {msg}")
def info(msg): print(f"  {BLU}ℹ️ {RST} {msg}")
def head(msg): print(f"\n{BLD}{GLD}{'═'*60}{RST}\n{BLD}  {msg}{RST}\n{BLD}{GLD}{'═'*60}{RST}")
def sub(msg):  print(f"\n{BLD}  ▸ {msg}{RST}")

# ─────────────────────────────────────────────────────────────────────────
# GLOBALNI REZULTATI
# ─────────────────────────────────────────────────────────────────────────
RESULTS = {'pass': 0, 'fail': 0, 'warn': 0}

def check(condition, pass_msg, fail_msg, warning=False):
    if condition:
        ok(pass_msg)
        RESULTS['pass'] += 1
    elif warning:
        warn(fail_msg)
        RESULTS['warn'] += 1
    else:
        fail(fail_msg)
        RESULTS['fail'] += 1
    return condition


# ══════════════════════════════════════════════════════════════════════════
# 1. TEMPLATE SYNTAX — Sve ključne template datoteke se parsiraju bez grešaka
# ══════════════════════════════════════════════════════════════════════════

head("1. TEMPLATE SYNTAX")

TEMPLATES_TO_CHECK = [
    'base.html',
    'base_shell.html',
    'konto/dashboard.html',
    'pos/dashboard.html',
    'limit_connect_ai/doktor_dashboard.html',
    'documents/arhiva_list.html',
    'includes/_panel_konto.html',
    'includes/_panel_doktor.html',
    'includes/_panel_pos.html',
    'includes/_panel_row.html',
    'includes/_panel_link.html',
]

for tpl in TEMPLATES_TO_CHECK:
    try:
        get_template(tpl)
        ok(f"{tpl}")
        RESULTS['pass'] += 1
    except Exception as e:
        fail(f"{tpl} — {str(e)[:80]}")
        RESULTS['fail'] += 1


# ══════════════════════════════════════════════════════════════════════════
# 2. BASE.HTML — Shell infrastruktura
# ══════════════════════════════════════════════════════════════════════════

head("2. BASE.HTML — Shell infrastruktura")

with open('templates/base.html', 'r') as f:
    BASE = f.read()

sub("CSS i JavaScript")
check('fenix-shell.css' in BASE,
      'fenix-shell.css učitan u base.html',
      'fenix-shell.css NEDOSTAJE u base.html')

check('FenixShell' in BASE and 'openRight' in BASE and 'closeRight' in BASE,
      'FenixShell JS objekt prisutan (openRight, closeRight)',
      'FenixShell JS NEDOSTAJE')

check('openJoker' in BASE and 'closeJoker' in BASE,
      'FenixShell.openJoker / closeJoker prisutni',
      'Joker funkcije NEDOSTAJU')

check("e.key === 'p'" in BASE or "e.key==='p'" in BASE,
      "Alt+P keyboard shortcut za desni panel",
      "Alt+P shortcut NEDOSTAJE")

check("e.key === 'Escape'" in BASE or "e.key==='Escape'" in BASE,
      "Esc tipka zatvara joker",
      "Esc handler NEDOSTAJE")

sub("HTML struktura")
check('id="shellRight"' in BASE,
      'shell-right aside prisutan (id=shellRight)',
      'shell-right aside NEDOSTAJE')

check('id="joker-overlay"' in BASE,
      'joker-overlay div prisutan',
      'joker-overlay NEDOSTAJE')

check('{% block shell_right_title %}' in BASE,
      '{% block shell_right_title %} blok postoji',
      'shell_right_title blok NEDOSTAJE')

check('{% block shell_right_content %}' in BASE,
      '{% block shell_right_content %} blok postoji',
      'shell_right_content blok NEDOSTAJE')

check('{% block shell_mode %}' in BASE,
      '{% block shell_mode %} blok postoji',
      'shell_mode blok NEDOSTAJE')

check('data-shell-mode' in BASE,
      'data-shell-mode atribut na .app-layout',
      'data-shell-mode NEDOSTAJE na .app-layout')

sub("Hamburger gumbi")
check('id="right-panel-btn"' in BASE,
      'Hamburger #2 — topbar desni panel gumb',
      'Hamburger #2 NEDOSTAJE (right-panel-btn)')

check('id="bottom-right-btn"' in BASE,
      'Hamburger #4 — mobile bottom nav panel gumb',
      'Hamburger #4 NEDOSTAJE (bottom-right-btn)')

check('openSidebar()' in BASE or 'toggleSidebar' in BASE,
      'Hamburger #1 — sidebar toggle prisutan',
      'Hamburger #1 NEDOSTAJE')

sub("right-panel-open klasa")
check('right-panel-open' in BASE,
      '.right-panel-open klasa se dodaje/skida u openRight/closeRight',
      '.right-panel-open NEDOSTAJE u JS funkcijama')

sub("Backwards kompatibilnost")
check('function toggleShellRight' in BASE,
      'Backwards alias toggleShellRight() postoji',
      'Backwards alias NEDOSTAJE')

check('function openShellRight' in BASE and 'function closeShellRight' in BASE,
      'Backwards aliasi openShellRight/closeShellRight postoje',
      'Backwards aliasi NEDOSTAJU')


# ══════════════════════════════════════════════════════════════════════════
# 3. DJANGO TEMPLATE BLOKOVI — Faza 3
# ══════════════════════════════════════════════════════════════════════════

head("3. DJANGO BLOKOVI — Faza 3 (konto, doktor, pos)")

MODUL_CHECKS = [
    {
        'name': 'konto/dashboard.html',
        'path': 'templates/konto/dashboard.html',
        'title_block': 'Financije',
        'include': '_panel_konto.html',
        'shell_mode': 'default',
    },
    {
        'name': 'doktor_dashboard.html',
        'path': 'templates/limit_connect_ai/doktor_dashboard.html',
        'title_block': 'Doktor',
        'include': '_panel_doktor.html',
        'shell_mode': 'default',
    },
    {
        'name': 'pos/dashboard.html',
        'path': 'templates/pos/dashboard.html',
        'title_block': 'POS Terminali',
        'include': '_panel_pos.html',
        'shell_mode': 'default',
    },
]

for m in MODUL_CHECKS:
    sub(m['name'])
    with open(m['path'], 'r') as f:
        src = f.read()

    check('block shell_right_title' in src,
          "block shell_right_title prisutan",
          "block shell_right_title NEDOSTAJE")

    check('block shell_right_content' in src,
          "block shell_right_content prisutan",
          "block shell_right_content NEDOSTAJE")

    check(m['include'] in src,
          f"include '{m['include']}' referenciran",
          f"include '{m['include']}' NEDOSTAJE")

    check("block shell_mode" in src,
          "block shell_mode prisutan",
          "block shell_mode NEDOSTAJE", warning=True)

    check('FenixShell.openRight()' in src,
          "auto-open panel na DOMContentLoaded",
          "auto-open NEDOSTAJE — panel se neće otvoriti", warning=True)

    # Provjeri da nema duplikata blokova (otvori-tag s imenom)
    title_count = src.count('{% block shell_right_title %}') + src.count("{% block shell_right_title%}")
    check(title_count == 1,
          f"shell_right_title blok definiran točno jednom ({title_count}x)",
          f"DUPLIKAT shell_right_title ({title_count}x) — Django greška!")

    content_count = src.count('{% block shell_right_content %}') + src.count("{% block shell_right_content%}")
    check(content_count == 1,
          f"shell_right_content blok definiran točno jednom ({content_count}x)",
          f"DUPLIKAT shell_right_content ({content_count}x) — Django greška!")


# ══════════════════════════════════════════════════════════════════════════
# 4. ARHIVA — JS Hook (Faza 2, ostaje na JS)
# ══════════════════════════════════════════════════════════════════════════

head("4. ARHIVA LIST — JS Hook")

with open('templates/documents/arhiva_list.html', 'r') as f:
    ARHIVA = f.read()

check('_hookDrawerData' in ARHIVA,
      '_hookDrawerData hook prisutan (auto-poziv iz openDrawer)',
      '_hookDrawerData hook NEDOSTAJE')

check('FenixShell.setRightPanel' in ARHIVA,
      'FenixShell.setRightPanel poziv u hook funkciji',
      'setRightPanel NEDOSTAJE u hooku')

check('doProknjizi' in ARHIVA,
      'Proknjiri gumb generiran u hook funkciji',
      'Proknjiri gumb NEDOSTAJE u hook')

check('FenixShell.closeRight()' in ARHIVA,
      'closeRight() pri zatvaranju drawera',
      'closeRight sinkronizacija NEDOSTAJE', warning=True)

check('FenixShell' in ARHIVA and 'window._hookDrawerData' in ARHIVA,
      'Hook dodijeljen na window objekt (dostupan globalno)',
      'Hook NIJE na window objektu — neće biti vidljiv iz openDrawer')


# ══════════════════════════════════════════════════════════════════════════
# 5. CSS — fenix-shell.css
# ══════════════════════════════════════════════════════════════════════════

head("5. CSS — fenix-shell.css")

with open('static/css/fenix-shell.css', 'r') as f:
    CSS = f.read()

sub("Right panel klase")
check('.shell-right' in CSS,
      '.shell-right stilovi postoje',
      '.shell-right NEDOSTAJE u CSS')

check('.shell-right.open' in CSS,
      '.shell-right.open stanje definirano',
      '.shell-right.open NEDOSTAJE')

check('.shell-right.collapsed' in CSS,
      '.shell-right.collapsed stanje definirano',
      '.shell-right.collapsed NEDOSTAJE')

check('right-panel-open' in CSS,
      '.right-panel-open CSS klasa za .main pomak (desktop)',
      '.right-panel-open NEDOSTAJE — panel neće pomicati sadržaj')

sub("Joker CSS")
check('#joker-overlay' in CSS or 'joker-active' in CSS,
      'Joker CSS prisutan (joker-active body klasa)',
      'Joker CSS NEDOSTAJE')

check('body.joker-active .bottom-tabs' in CSS,
      'Joker sakriva bottom-tabs',
      'Joker ne skriva bottom-tabs')

check('body.joker-active .topbar' in CSS,
      'Joker sakriva topbar',
      'Joker ne skriva topbar')

sub("Mobile responsive")
check('@media (max-width: 767px)' in CSS or '@media(max-width:767px)' in CSS,
      'Mobile breakpoint za right panel (slide-up drawer)',
      'Mobile breakpoint NEDOSTAJE')

check('translateY(100%)' in CSS,
      'Mobile drawer slide-up animacija prisutna',
      'Mobile drawer animacija NEDOSTAJE', warning=True)

sub("Hamburger CSS")
check('.shell-hamburger' in CSS,
      '.shell-hamburger stilovi postoje',
      '.shell-hamburger NEDOSTAJE')


# ══════════════════════════════════════════════════════════════════════════
# 6. HTTP LIVE PROVJERE — Autentificirani zahtjevi
# ══════════════════════════════════════════════════════════════════════════

head("6. HTTP LIVE — Provjera renderiranja stranica")

try:
    client = Client()
    logged_in = client.force_login(User.objects.get(username='marija.brtan'))

    ROUTES = [
        ('/hr/konto/',             'konto/dashboard',    ['id="shellRight"', 'fenix-shell.css', 'FenixShell', 'Financije']),
        ('/hr/ai-cockpit/doktor/', 'doktor_dashboard',   ['id="shellRight"', 'fenix-shell.css', 'Dijagnoza']),
        ('/hr/pos/',               'pos/dashboard',      ['id="shellRight"', 'fenix-shell.css', 'Terminali']),
        ('/hr/documents/arhiva/',  'arhiva_list',        ['_hookDrawerData', 'FenixShell', 'id="shellRight"']),
        ('/hr/',                   'dashboard',          ['fenix-shell.css', 'id="shellRight"', 'id="joker-overlay"']),
    ]

    for url, name, must_contain in ROUTES:
        sub(f"{name} ({url})")
        try:
            resp = client.get(url, follow=True)
            check(resp.status_code == 200,
                  "HTTP 200",
                  f"HTTP {resp.status_code} — stranica ne radi!")

            content = resp.content.decode('utf-8', errors='replace')

            for needle in must_contain:
                check(needle in content,
                      f"'{needle}' prisutan u rendered HTML",
                      f"'{needle}' NEDOSTAJE u rendered HTML — shell nije integriran!")

            # Provjeri da nema template grešaka
            check('TemplateSyntaxError' not in content and 'TemplateDoesNotExist' not in content,
                  "Nema template grešaka u outputu",
                  "TEMPLATE GREŠKA u rendered outputu!")

        except (UnicodeDecodeError, ValueError) as e:
            fail(f"Iznimka za {url}: {e}")
            RESULTS['fail'] += 1

except (UnicodeDecodeError, ValueError) as e:
    warn(f"HTTP provjere preskočene — greška pri login: {e}")
    RESULTS['warn'] += 1


# ══════════════════════════════════════════════════════════════════════════
# 7. PANEL INCLUDE FAJLOVI — Sintaksa i sadržaj
# ══════════════════════════════════════════════════════════════════════════

head("7. PANEL INCLUDE FAJLOVI")

PANEL_CHECKS = {
    'includes/_panel_konto.html': [
        ('total_bank', 'Žiro saldo varijabla'),
        ('month_inflow', 'Priljevi varijabla'),
        ('pnl.profit_loss', 'P&L varijabla'),
        ('_panel_row.html', 'Koristi _panel_row helper'),
        ('_panel_link.html', 'Koristi _panel_link helper'),
        ('konto:transactions', 'Link na Transakcije'),
        ('konto:report_vat', 'Link na PDV'),
    ],
    'includes/_panel_doktor.html': [
        ('report.overall_score', 'Score varijabla'),
        ('report.ai_summary', 'AI sažetak varijabla'),
        ('report.category_scores', 'Kategorije varijabla'),
        ('report.recommendations', 'Preporuke varijabla'),
        ('limit_connect_ai:doktor_dashboard', 'Link na puni izvještaj'),
        ('report.status == "done"', 'Uvjetni prikaz (done stanje)'),
        ('report.status == "pending"', 'Uvjetni prikaz (pending stanje)'),
    ],
    'includes/_panel_pos.html': [
        ('terminals', 'Terminals varijabla u for petlji'),
        ('terminal.name', 'Terminal naziv'),
        ('terminal.active_session', 'Smjena status'),
        ('pos:pos_joker', 'Link na POS joker'),
        ('pos:new_terminal', 'Link za novi terminal'),
    ],
    'includes/_panel_row.html': [
        ('{{ label }}', 'Label varijabla'),
        ('{{ val', 'Val varijabla'),
        ('{{ color', 'Color varijabla'),
    ],
    'includes/_panel_link.html': [
        ('{{ href }}', 'Href varijabla'),
        ('{{ icon }}', 'Icon varijabla'),
        ('{{ label }}', 'Label varijabla'),
    ],
}

for panel_path, checks in PANEL_CHECKS.items():
    sub(panel_path)
    try:
        with open(f'templates/{panel_path}', 'r') as f:
            src = f.read()
        for needle, desc in checks:
            check(needle in src, desc, f"'{needle}' NEDOSTAJE u {panel_path}")
    except FileNotFoundError:
        fail(f"FAJL NE POSTOJI: templates/{panel_path}")
        RESULTS['fail'] += 1


# ══════════════════════════════════════════════════════════════════════════
# 8. JOKER FULLSCREEN — Funkcionalnost
# ══════════════════════════════════════════════════════════════════════════

head("8. JOKER FULLSCREEN MODE")

check('id="joker-overlay"' in BASE,
      'joker-overlay div postoji u base.html',
      'joker-overlay NEDOSTAJE')

check('id="joker-content"' in BASE,
      'joker-content div postoji (za ubacivanje sadržaja)',
      'joker-content NEDOSTAJE')

check('id="joker-title"' in BASE,
      'joker-title span postoji',
      'joker-title NEDOSTAJE')

check('location.search.includes(\'joker=1\')' in BASE,
      '?joker=1 URL param auto-otvara joker',
      '?joker=1 param NEDOSTAJE')

check("e.key === 'Escape'" in BASE,
      'Esc tipka zatvara joker overlay',
      'Esc handler NEDOSTAJE')

check('jokerFadeIn' in CSS or '@keyframes jokerFadeIn' in CSS,
      'jokerFadeIn CSS animacija definirana',
      'jokerFadeIn animacija NEDOSTAJE', warning=True)

# POS joker.html provjera
try:
    with open('templates/pos/joker.html', 'r') as f:
        joker_src = f.read()
    check('fullscreen' in joker_src or 'joker' in joker_src.lower(),
          'pos/joker.html postoji i ima fullscreen sadržaj',
          'pos/joker.html nema fullscreen elemente', warning=True)
    RESULTS['pass'] += 1
except FileNotFoundError:
    fail('templates/pos/joker.html ne postoji!')
    RESULTS['fail'] += 1


# ══════════════════════════════════════════════════════════════════════════
# 9. GIT STANJE — Sve je commited
# ══════════════════════════════════════════════════════════════════════════

head("9. GIT STANJE")

import subprocess

result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
uncommited = [l for l in result.stdout.strip().split('\n') if l.strip()]
uncommited_shell = [l for l in uncommited if any(x in l for x in ['base.html','shell','panel','konto','doktor','pos'])]

check(len(uncommited_shell) == 0,
      f"Svi shell fajlovi su commited ({len(uncommited)} ukupno uncommited)",
      f"SHELL FAJLOVI NISU COMMITED: {uncommited_shell}")

result2 = subprocess.run(['git', 'log', '--oneline', '-5'], capture_output=True, text=True)
info("Zadnjih 5 commitova:\n    " + result2.stdout.replace('\n', '\n    '))


# ══════════════════════════════════════════════════════════════════════════
# 10. DJANGO SYSTEM CHECK
# ══════════════════════════════════════════════════════════════════════════

head("10. DJANGO SYSTEM CHECK")

result = subprocess.run(
    ['venv/bin/python', 'manage.py', 'check', '--deploy'],
    capture_output=True, text=True, cwd='/var/www/fina-connect'
)
output = result.stdout + result.stderr
errors   = [l for l in output.split('\n') if 'ERROR' in l]
warnings = [l for l in output.split('\n') if 'WARNING' in l]

check(len(errors) == 0,
      "Django check: 0 ERROR-a",
      f"Django check: {len(errors)} ERROR-a — {errors}")

check(len(warnings) <= 5,
      f"Django check: {len(warnings)} upozorenja (prihvatljivo)",
      f"Django check: {len(warnings)} upozorenja — provjeri",
      warning=True)

info(f"System check: {len(errors)} errora, {len(warnings)} warninga")


# ══════════════════════════════════════════════════════════════════════════
# FINALNI IZVJEŠTAJ
# ══════════════════════════════════════════════════════════════════════════

head("FINALNI IZVJEŠTAJ")

total = RESULTS['pass'] + RESULTS['fail'] + RESULTS['warn']
score = int(RESULTS['pass'] / max(total, 1) * 100)

print(f"""
  {GRN}✅ Prošlo:     {RESULTS['pass']:3d}{RST}
  {RED}❌ Palo:       {RESULTS['fail']:3d}{RST}
  {YLW}⚠️  Upozorenja: {RESULTS['warn']:3d}{RST}
  ─────────────────────
  {BLD}📊 Ukupno:    {total:3d} provjera{RST}
  {BLD}🎯 Rezultat:  {score}% ({RESULTS['pass']}/{total}){RST}
""")

if RESULTS['fail'] == 0:
    print(f"  {GRN}{BLD}🏆 SVE PROVJERE PROŠLE — Shell infrastruktura je OK!{RST}\n")
elif RESULTS['fail'] <= 3:
    print(f"  {YLW}{BLD}⚠️  {RESULTS['fail']} MINOR PROBLEMA — provjeri gore označene{RST}\n")
else:
    print(f"  {RED}{BLD}🚨 {RESULTS['fail']} KRITIČNIH GREŠAKA — shell nije u redu!{RST}\n")

sys.exit(0 if RESULTS['fail'] == 0 else 1)
