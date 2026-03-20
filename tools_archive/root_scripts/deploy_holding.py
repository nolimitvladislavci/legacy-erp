import os
import shutil

BASE_DIR = '/var/www/fina-connect'
WEBSITE_DIR = os.path.join(BASE_DIR, 'website')
TPL_DIR = os.path.join(WEBSITE_DIR, 'templates', 'website')

# 1. Kreiranje backupa
def backup(filepath):
    if os.path.exists(filepath):
        shutil.copy2(filepath, filepath + '.bak')

backup(os.path.join(WEBSITE_DIR, 'urls.py'))
backup(os.path.join(WEBSITE_DIR, 'views.py'))
backup(os.path.join(TPL_DIR, 'homepage.html'))

# 2. Ažuriranje website/urls.py
urls_content = """from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('bau/', views.bau_page, name='bau_page'),  # NOVA RUTA ZA KLEINANZEIGEN
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('hitna-intervencija/', views.hitna_intervencija, name='hitna_intervencija'),
    path('hitna-intervencija/hvala/', views.hitna_hvala, name='hitna_hvala'),
    path('video-galerija/', views.video_galerija, name='video_galerija'),
    path('hr/', views.viskovic_hr, name='viskovic_hr'),
]
"""
with open(os.path.join(WEBSITE_DIR, 'urls.py'), 'w', encoding='utf-8') as f:
    f.write(urls_content)

# 3. Ažuriranje website/views.py (Dodavanje bau_page)
with open(os.path.join(WEBSITE_DIR, 'views.py'), 'r', encoding='utf-8') as f:
    views_content = f.read()

if "def bau_page" not in views_content:
    # Mijenjamo i homepage view da renderira pravi homepage.html umjesto starog
    views_content = views_content.replace(
        'return render(request, "viskovic_group_index.html")',
        'return render(request, "website/homepage.html")'
    )
    
    nova_funkcija = """

def bau_page(request):
    \"\"\"Landing stranica za građevinu i sanacije (za oglasnike)\"\"\"
    return render(request, 'website/bau.html')
"""
    views_content += nova_funkcija
    with open(os.path.join(WEBSITE_DIR, 'views.py'), 'w', encoding='utf-8') as f:
        f.write(views_content)

# 4. Ažuriranje homepage.html (Povezivanje linka na BAU podstranicu)
homepage_path = os.path.join(TPL_DIR, 'homepage.html')
with open(homepage_path, 'r', encoding='utf-8') as f:
    hp_html = f.read()

# Zamijeni prazan href="#" s pravim linkom za Visković BAU karticu
hp_html = hp_html.replace('<a href="#" class="brand-card featured reveal">', '<a href="/bau/" class="brand-card featured reveal">')
with open(homepage_path, 'w', encoding='utf-8') as f:
    f.write(hp_html)


# 5. Kreiranje potpuno nove BAU podstranice (bau.html) s izvornim CSS-om i njemačkim tekstom
bau_html_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Badezimmersanierung & Innenausbau — Visković BAU</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Barlow:wght@300;400;500;600;700&family=Barlow+Condensed:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --black:   #0a0a0a; --dark:    #111214; --surface: #181a1d;
            --border:  #252830; --muted:   #4a5060; --light:   #9aa0b0;
            --white:   #f0ede8; --gold:    #c9a84c; --gold2:   #e8c96a;
            --red:     #c0392b;
        }
        html { scroll-behavior: smooth; }
        body {
            background: var(--black); color: var(--white);
            font-family: 'Barlow', sans-serif; font-weight: 300;
            overflow-x: hidden; cursor: default;
        }
        body::before {
            content: ''; position: fixed; inset: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
            pointer-events: none; z-index: 9999; opacity: 0.4;
        }
        /* HEADER */
        header {
            position: fixed; top: 0; left: 0; right: 0; z-index: 100;
            padding: 0 48px; display: flex; align-items: center; justify-content: space-between;
            height: 72px; background: linear-gradient(to bottom, rgba(10,10,10,0.98), rgba(10,10,10,0));
            backdrop-filter: blur(0px); transition: backdrop-filter 0.4s, background 0.4s;
        }
        header.scrolled { background: rgba(10,10,10,0.95); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); }
        .header-logo {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 1.1rem;
            letter-spacing: 4px; color: var(--white); text-decoration: none; text-transform: uppercase;
        }
        .header-logo span { color: var(--gold); }
        nav { display: flex; align-items: center; gap: 36px; }
        nav a { font-size: 0.78rem; letter-spacing: 2.5px; text-transform: uppercase; color: var(--light); text-decoration: none; transition: color 0.2s; }
        nav a:hover { color: var(--white); }
        /* HERO */
        .hero { min-height: 100vh; display: flex; flex-direction: column; justify-content: flex-end; padding: 0 48px 80px; position: relative; overflow: hidden; }
        .hero-bg {
            position: absolute; inset: 0;
            background: radial-gradient(ellipse 80% 60% at 70% 40%, rgba(201,168,76,0.06) 0%, transparent 70%),
                        radial-gradient(ellipse 50% 80% at 10% 80%, rgba(192,57,43,0.04) 0%, transparent 60%),
                        linear-gradient(160deg, #0a0a0a 0%, #0f1115 50%, #0a0a0a 100%);
        }
        .hero-lines::before, .hero-lines::after {
            content: ''; position: absolute; top: 0; width: 1px; height: 100%;
            background: linear-gradient(to bottom, transparent, var(--border) 20%, var(--border) 80%, transparent);
        }
        .hero-lines::before { left: 48px; } .hero-lines::after { right: 48px; }
        .hero-eyebrow {
            font-family: 'Barlow Condensed', sans-serif; font-size: 0.7rem; letter-spacing: 5px;
            text-transform: uppercase; color: var(--gold); margin-bottom: 24px; display: flex; align-items: center; gap: 16px;
        }
        .hero-eyebrow::before { content: ''; display: block; width: 40px; height: 1px; background: var(--gold); }
        .hero-title {
            font-family: 'Cormorant Garamond', serif; font-size: clamp(48px, 7vw, 100px);
            font-weight: 300; line-height: 0.95; letter-spacing: -2px; color: var(--white); max-width: 900px;
        }
        .hero-title em { font-style: italic; color: var(--gold); }
        .hero-title strong { font-weight: 600; display: block; }
        .hero-sub { margin-top: 32px; font-size: 1.1rem; font-weight: 300; color: var(--light); max-width: 550px; line-height: 1.7; }
        .hero-actions { margin-top: 48px; display: flex; gap: 16px; align-items: center; }
        .btn-primary { padding: 14px 36px; background: var(--gold); color: var(--black); font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 0.85rem; letter-spacing: 2px; text-transform: uppercase; text-decoration: none; transition: background 0.2s, transform 0.2s; display: inline-block; }
        .btn-primary:hover { background: var(--gold2); transform: translateY(-2px); }
        
        /* STATS BAR */
        .stats-bar { background: var(--surface); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 0 48px; display: flex; }
        .stat-item { flex: 1; padding: 36px 24px; border-right: 1px solid var(--border); text-align: center; }
        .stat-item:last-child { border-right: none; }
        .stat-num { font-family: 'Cormorant Garamond', serif; font-size: 2.8rem; font-weight: 300; color: var(--gold); line-height: 1; }
        .stat-label { font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); margin-top: 8px; }

        /* ABOUT / SERVICES */
        section { padding: 120px 48px; }
        .about-section { background: var(--black); position: relative; }
        .section-eyebrow { font-family: 'Barlow Condensed', sans-serif; font-size: 0.68rem; letter-spacing: 5px; text-transform: uppercase; color: var(--gold); margin-bottom: 20px; display: flex; align-items: center; gap: 14px; }
        .section-eyebrow::before { content: ''; width: 30px; height: 1px; background: var(--gold); }
        .section-title { font-family: 'Cormorant Garamond', serif; font-size: clamp(36px, 5vw, 64px); font-weight: 300; line-height: 1.1; }
        .section-title em { font-style: italic; color: var(--gold); }
        .about-grid { display: grid; grid-template-columns: 1fr 1.2fr; gap: 100px; align-items: start; margin-top: 60px; }
        .about-quote { font-family: 'Cormorant Garamond', serif; font-size: clamp(22px, 3vw, 36px); font-weight: 300; font-style: italic; color: var(--white); line-height: 1.5; border-left: 2px solid var(--gold); padding-left: 32px; margin-bottom: 40px; }
        .about-text { font-size: 0.95rem; color: var(--light); line-height: 1.9; margin-bottom: 20px; }
        
        .values-list { list-style: none; }
        .values-list li { padding: 28px 0; border-bottom: 1px solid var(--border); display: flex; gap: 24px; align-items: flex-start; }
        .values-list li:first-child { border-top: 1px solid var(--border); }
        .value-num { font-family: 'Cormorant Garamond', serif; font-size: 1.8rem; color: var(--gold); line-height: 1; flex-shrink: 0; width: 40px; }
        .value-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 1rem; letter-spacing: 1.5px; text-transform: uppercase; color: var(--white); margin-bottom: 8px; }
        .value-text { font-size: 0.875rem; color: var(--light); line-height: 1.7; }

        /* CONTACT */
        .cta-section { background: var(--surface); border-top: 1px solid var(--border); padding: 120px 48px; text-align: center; }
        .cta-box { max-width: 600px; margin: 0 auto; }

        /* FOOTER */
        footer { background: var(--black); border-top: 1px solid var(--border); padding: 40px 48px; display: flex; justify-content: space-between; align-items: center; }
        .footer-brand { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 0.85rem; letter-spacing: 4px; color: var(--muted); }
        .footer-brand span { color: var(--gold); }
        .footer-copy { font-size: 0.72rem; color: var(--muted); letter-spacing: 1px; }

        @media (max-width: 900px) {
            header { padding: 15px 24px; }
            nav { gap: 20px; }
            nav a:not(.btn-primary) { display: none; }
            .hero { padding: 120px 24px 60px; }
            .stats-bar { padding: 0 24px; flex-wrap: wrap; }
            .stat-item { flex: 50%; border-bottom: 1px solid var(--border); border-right: none; }
            .about-grid { grid-template-columns: 1fr; gap: 40px; }
            section { padding: 80px 24px; }
            .cta-section { padding: 80px 24px; }
            footer { flex-direction: column; gap: 16px; text-align: center; padding: 32px 24px; }
        }
    </style>
</head>
<body>

<header id="header">
    <a href="/" class="header-logo">VISKOVIĆ <span>BAU</span></a>
    <nav>
        <a href="/">← Zurück zur Gruppe</a>
        <a href="#kontakt" class="btn-primary" style="padding: 10px 20px; font-size: 0.75rem;">Kontakt</a>
    </nav>
</header>

<section class="hero">
    <div class="hero-bg"></div>
    <div class="hero-lines"></div>
    
    <div class="hero-eyebrow">Stuttgart & Umgebung</div>
    <h1 class="hero-title">
        Schlüsselfertige<br>
        <em>Badsanierung &</em>
        <strong>Innenausbau.</strong>
    </h1>
    <p class="hero-sub">
        Kein Stress mit der Koordination vieler verschiedener Handwerker. 
        Wir übernehmen Ihr komplettes Renovierungsprojekt von der ersten Idee bis zur Endreinigung – alles aus einer Hand.
    </p>
    <div class="hero-actions">
        <a href="#kontakt" class="btn-primary" style="background: var(--white); color: var(--black);">Kostenlose Besichtigung anfragen</a>
    </div>
</section>

<div class="stats-bar">
    <div class="stat-item">
        <div class="stat-num">100%</div>
        <div class="stat-label">Termintreue</div>
    </div>
    <div class="stat-item">
        <div class="stat-num">1</div>
        <div class="stat-label">Ansprechpartner</div>
    </div>
    <div class="stat-item">
        <div class="stat-num">20+</div>
        <div class="stat-label">Jahre Erfahrung</div>
    </div>
    <div class="stat-item">
        <div class="stat-num">0</div>
        <div class="stat-label">Versteckte Kosten</div>
    </div>
</div>

<section class="about-section">
    <div class="section-eyebrow">Unsere Leistungen</div>
    <h2 class="section-title">Ihre Vision,<br><em>unsere</em> Umsetzung.</h2>

    <div class="about-grid">
        <div class="about-left">
            <blockquote class="about-quote">
                "Sauberkeit, Präzision und faire Preise. Wir verlassen Ihre Baustelle erst, wenn Sie 100% zufrieden sind."
            </blockquote>
            <p class="about-text">
                Eine Renovierung muss nicht stressig sein. Als professionelles Bauunternehmen aus der Region koordinieren wir sämtliche Gewerke. Sie sagen uns, wie Ihr Traumbad oder Ihre Wohnung aussehen soll, und wir erledigen den Rest.
            </p>
        </div>
        <div class="about-right">
            <ul class="values-list">
                <li>
                    <div class="value-num">I</div>
                    <div class="value-content">
                        <div class="value-title">Komplette Badsanierung</div>
                        <div class="value-text">Abriss, fachgerechte Entsorgung, Neuinstallation von Sanitäranlagen und Wasserleitungen. Walk-in Duschen und exakte Endmontage.</div>
                    </div>
                </li>
                <li>
                    <div class="value-num">II</div>
                    <div class="value-content">
                        <div class="value-title">Professionelle Fliesenlegerarbeiten</div>
                        <div class="value-text">Verlegung von XXL-Fliesen, Mosaik und Naturstein. Exakte Jollyschnitte (Gehrungskanten) für perfekte Ecken ohne Profilschienen.</div>
                    </div>
                </li>
                <li>
                    <div class="value-num">III</div>
                    <div class="value-content">
                        <div class="value-title">Trockenbau & Innenausbau</div>
                        <div class="value-text">Stellen von Trennwänden, Abhängen von Decken, Schallschutz und moderne Raumaufteilung.</div>
                    </div>
                </li>
                <li>
                    <div class="value-num">IV</div>
                    <div class="value-content">
                        <div class="value-title">Maler- & Bodenarbeiten</div>
                        <div class="value-text">Hochwertige Spachtelarbeiten (Q3/Q4), Malervlies, Streichen sowie das Verlegen von Laminat und Parkett.</div>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</section>

<div class="cta-section" id="kontakt">
    <div class="cta-box">
        <div class="section-eyebrow" style="justify-content: center;">Jetzt Kontakt aufnehmen</div>
        <h2 class="section-title" style="margin-bottom: 24px;">Bereit für Ihr <em>neues</em> Zuhause?</h2>
        <p class="about-text" style="text-align: center; margin-bottom: 40px;">
            Rufen Sie uns direkt an oder schreiben Sie uns eine Nachricht. Wir kommen gerne unverbindlich bei Ihnen vorbei, um den Aufwand einzuschätzen.
        </p>
        <div style="display: flex; flex-direction: column; gap: 16px; align-items: center;">
            <a href="tel:+4915234209056" class="btn-primary" style="font-size: 1.2rem; width: 100%; max-width: 400px; padding: 20px;">📞 015 234 209 056</a>
            <a href="mailto:viskovic.bau@gmail.com" style="color: var(--gold); text-decoration: none; font-size: 1.1rem; margin-top: 10px;">viskovic.bau@gmail.com</a>
        </div>
    </div>
</div>

<footer>
    <div class="footer-brand">VISKOVIĆ <span>BAU</span></div>
    <div class="footer-copy">© 2026 Visković Group · Ein Unternehmen der Visković Group</div>
</footer>

<script>
    const header = document.getElementById('header');
    window.addEventListener('scroll', () => {
        header.classList.toggle('scrolled', window.scrollY > 50);
    });
</script>
</body>
</html>
"""

with open(os.path.join(TPL_DIR, 'bau.html'), 'w', encoding='utf-8') as f:
    f.write(bau_html_content)

# 6. Restart servera da primijeni URL promjene
os.system("supervisorctl restart fina-connect")
print("✅ USPJEH! Holding arhitektura i nova /bau stranica su kreirane. Server je restartan.")
