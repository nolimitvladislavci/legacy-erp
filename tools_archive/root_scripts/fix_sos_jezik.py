import os
import shutil

BASE_DIR = '/var/www/fina-connect'
FORMS_FILE = os.path.join(BASE_DIR, 'website', 'forms.py')
HITNA_HTML = os.path.join(BASE_DIR, 'website', 'templates', 'website', 'hitna_intervencija.html')
HVALA_HTML = os.path.join(BASE_DIR, 'website', 'templates', 'website', 'hitna_hvala.html')

# 1. BACKUP
if os.path.exists(FORMS_FILE): shutil.copy2(FORMS_FILE, FORMS_FILE + '.bak_sos')
if os.path.exists(HITNA_HTML): shutil.copy2(HITNA_HTML, HITNA_HTML + '.bak_sos')
if os.path.exists(HVALA_HTML): shutil.copy2(HVALA_HTML, HVALA_HTML + '.bak_sos')

# 2. POPRAVAK FORMS.PY (Postavljamo čisti Njemački)
forms_content = """from django import forms
from .models import HitnaIntervencija

class HitnaIntervencijaForm(forms.ModelForm):
    class Meta:
        model = HitnaIntervencija
        fields = ['ime', 'telefon', 'email', 'adresa', 'grad', 'drzava', 'vrsta', 'opis', 'hitnost']
        widgets = {
            'ime':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Vor- und Nachname'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+49 ...', 'type': 'tel'}),
            'email':   forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@beispiel.de'}),
            'adresa':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Straße und Hausnummer'}),
            'grad':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Stadt / PLZ'}),
            'drzava':  forms.Select(attrs={'class': 'form-select'},
                                    choices=[('DE','Deutschland'), ('AT','Österreich'),
                                             ('CH','Schweiz'), ('HR','Kroatien')]),
            'vrsta':   forms.Select(attrs={'class': 'form-select'}),
            'opis':    forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                             'placeholder': 'Beschreiben Sie das Problem so genau wie möglich...'}),
            'hitnost': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'ime':     'Vor- und Nachname',
            'telefon': 'Telefon (erforderlich)',
            'email':   'E-Mail',
            'adresa':  'Adresse',
            'grad':    'Stadt / PLZ',
            'drzava':  'Land',
            'vrsta':   'Art des Notfalls',
            'opis':    'Problembeschreibung',
            'hitnost': 'Dringend — Ich benötige sofortige Hilfe',
        }
"""
with open(FORMS_FILE, 'w', encoding='utf-8') as f:
    f.write(forms_content)

# 3. POPRAVAK HITNA_INTERVENCIJA.HTML (Njemački + Prave varijable + Gumb za jezik)
hitna_html_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Notfall / 24/7 Notdienst — Visković Group</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
  
  /* Lang Switcher */
  .lang-switcher { position: absolute; top: 20px; right: 20px; display: flex; gap: 8px; z-index: 100;}
  .lang-btn { background: #1e293b; color: #94a3b8; border: 1px solid #334155; padding: 4px 12px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; text-decoration: none; transition: all 0.2s; }
  .lang-btn.active { background: #c9a84c; color: #0a0a0a; border-color: #c9a84c; }
  .lang-btn:hover:not(.active) { color: #e2e8f0; border-color: #64748b; }

  .hero-notfall {
    background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 50%, #1e293b 100%);
    padding: 60px 0 40px;
    text-align: center;
    position: relative;
  }
  .hero-notfall .notfall-icon { font-size: 4rem; animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.1)} }
  .phone-big { font-size: 2.2rem; font-weight: 700; color: #fbbf24; text-decoration: none; }
  .phone-big:hover { color: #f59e0b; }
  .card-form {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 2rem;
  }
  .form-control, .form-select {
    background: #0f172a;
    border: 1px solid #334155;
    color: #e2e8f0;
    border-radius: 8px;
  }
  .form-control:focus, .form-select:focus {
    background: #0f172a;
    border-color: #ef4444;
    color: #e2e8f0;
    box-shadow: 0 0 0 0.2rem rgba(239,68,68,.25);
  }
  .form-control::placeholder { color: #64748b; }
  .btn-notfall {
    background: #ef4444;
    color: white;
    border: none;
    padding: 14px 40px;
    font-size: 1.1rem;
    font-weight: 600;
    border-radius: 8px;
    width: 100%;
    transition: background .2s;
  }
  .btn-notfall:hover { background: #dc2626; color: white; }
  .btn-notfall:disabled { background: #7f1d1d; color: #cbd5e1; cursor: not-allowed; }
  .badge-hitno {
    display: inline-block;
    background: #ef4444;
    color: white;
    padding: 4px 14px;
    border-radius: 99px;
    font-size: .85rem;
    font-weight: 600;
    animation: pulse 1.5s infinite;
  }
  label { color: #cbd5e1; font-size: .9rem; margin-bottom: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;}
  .form-check-label { color: #fbbf24; font-weight: 600; text-transform: none; letter-spacing: normal;}
  .nav-back { color: #94a3b8; text-decoration: none; font-size: .9rem; }
  .nav-back:hover { color: #e2e8f0; }
  .garantie-strip {
    background: #1e293b;
    border-top: 1px solid #334155;
    padding: 1rem 0;
    text-align: center;
    color: #94a3b8;
    font-size: .85rem;
  }
  .garantie-strip span { color: #22c55e; margin: 0 1rem; }
  select option { background: #1e293b; color: #e2e8f0; }
</style>
</head>
<body>

<div class="hero-notfall">
  <div class="lang-switcher">
      <a href="?lang=de" class="lang-btn active">DE</a>
      <a href="?lang=hr" class="lang-btn" onclick="alert('Prijevod u pripremi / Übersetzung in Vorbereitung'); return false;">HR</a>
      <a href="?lang=en" class="lang-btn" onclick="alert('Translation in progress'); return false;">EN</a>
  </div>

  <div class="notfall-icon">🚨</div>
  <h1 class="mt-3 mb-1 fw-bold" style="font-size:2rem">24/7 Notdienst</h1>
  <p class="text-danger mb-3"><span class="badge-hitno">Immer verfügbar</span></p>
  <p class="mb-2" style="color:#94a3b8">Direkt anrufen — wir reagieren sofort:</p>
  <a href="tel:{{ site_settings.phone_1_number|default:'+4915234209056' }}" class="phone-big">📞 {{ site_settings.phone_1_number|default:'+49 15 234 209 056' }}</a>
  <p class="mt-4" style="color:#94a3b8;font-size:.9rem">
    Oder füllen Sie das Formular aus und wir melden uns innerhalb von 15 Minuten
  </p>
</div>

<div class="container py-5" style="max-width:680px">
  <a href="/" class="nav-back">← Zurück zur Startseite</a>

  <div class="card-form mt-4">
    <h2 class="mb-4 fw-semibold" style="font-size:1.3rem">Anfrage für Notdiensteinsatz</h2>

    {% if messages %}
      {% for msg in messages %}
        <div class="alert alert-success">{{ msg }}</div>
      {% endfor %}
    {% endif %}

    <form method="post" id="hitnaForm" novalidate>
      {% csrf_token %}

      <div class="row g-3">
        <div class="col-12">
          {{ form.ime.label_tag }}
          {{ form.ime }}
          {% if form.ime.errors %}<div class="text-danger small mt-1">{{ form.ime.errors|join:", " }}</div>{% endif %}
        </div>

        <div class="col-md-6">
          {{ form.telefon.label_tag }}
          {{ form.telefon }}
          {% if form.telefon.errors %}<div class="text-danger small mt-1">{{ form.telefon.errors|join:", " }}</div>{% endif %}
        </div>
        <div class="col-md-6">
          {{ form.email.label_tag }}
          {{ form.email }}
        </div>

        <div class="col-md-8">
          {{ form.adresa.label_tag }}
          {{ form.adresa }}
        </div>
        <div class="col-md-4">
          {{ form.grad.label_tag }}
          {{ form.grad }}
        </div>

        <div class="col-md-4">
          {{ form.drzava.label_tag }}
          {{ form.drzava }}
        </div>
        <div class="col-md-8">
          {{ form.vrsta.label_tag }}
          {{ form.vrsta }}
        </div>

        <div class="col-12">
          {{ form.opis.label_tag }}
          {{ form.opis }}
          {% if form.opis.errors %}<div class="text-danger small mt-1">{{ form.opis.errors|join:", " }}</div>{% endif %}
        </div>

        <div class="col-12">
          <div class="form-check">
            {{ form.hitnost }}
            <label class="form-check-label" for="{{ form.hitnost.id_for_label }}">
              ⚡ {{ form.hitnost.label }}
            </label>
          </div>
        </div>

        <div class="col-12 mt-4">
          <button type="submit" class="btn btn-notfall" id="submitBtn">
            <i class="fas fa-paper-plane"></i> Anfrage senden
          </button>
          <p class="text-center mt-3" style="color:#64748b;font-size:.8rem">
            Ihre Daten werden ausschließlich zur Bearbeitung der Anfrage verwendet.
          </p>
        </div>
      </div>
    </form>
  </div>

  <div class="row g-3 mt-4">
    <div class="col-md-4">
      <div class="text-center p-3" style="background:#1e293b;border-radius:10px">
        <div style="font-size:1.8rem">⚡</div>
        <div class="fw-semibold mt-1">Schnelle Reaktion</div>
        <div style="color:#94a3b8;font-size:.85rem">Antwort in 15 Min</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="text-center p-3" style="background:#1e293b;border-radius:10px">
        <div style="font-size:1.8rem">🕐</div>
        <div class="fw-semibold mt-1">24/7 Verfügbarkeit</div>
        <div style="color:#94a3b8;font-size:.85rem">Wochenenden & Feiertage</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="text-center p-3" style="background:#1e293b;border-radius:10px">
        <div style="font-size:1.8rem">✅</div>
        <div class="fw-semibold mt-1">Zertifiziertes Team</div>
        <div style="color:#94a3b8;font-size:.85rem">15+ Jahre Erfahrung</div>
      </div>
    </div>
  </div>
</div>

<div class="garantie-strip">
  <span>⚡ Reaktion in 15 Min</span>
  <span>🔒 Datenschutz</span>
  <span>✅ Zertifizierter Betrieb</span>
</div>

<script>
document.getElementById('hitnaForm').addEventListener('submit', function(e) {
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Wird gesendet...';
});
</script>
</body>
</html>
"""
with open(HITNA_HTML, 'w', encoding='utf-8') as f:
    f.write(hitna_html_content)

# 4. POPRAVAK HITNA_HVALA.HTML (Njemački + Prave varijable)
hvala_html_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Anfrage erhalten — Visković Group</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif;
         display:flex; flex-direction:column; min-height:100vh; justify-content:center; align-items:center; }
  .card-hvala { background: #1e293b; border: 1px solid #22c55e; border-radius: 16px;
                padding: 3rem 2.5rem; text-align: center; max-width: 500px; }
  .check-icon { font-size: 4rem; animation: pop .5s ease; }
  @keyframes pop { 0%{transform:scale(0)} 80%{transform:scale(1.1)} 100%{transform:scale(1)} }
  .phone-link { color: #fbbf24; font-size: 1.5rem; font-weight: 700; text-decoration: none; }
  .phone-link:hover { color: #f59e0b; }
  .btn-back { background: #334155; color: #e2e8f0; border: none; padding: 10px 28px;
              border-radius: 8px; text-decoration: none; display: inline-block; margin-top: 1.5rem; }
  .btn-back:hover { background: #475569; color: #e2e8f0; }
</style>
</head>
<body>
<div class="card-hvala">
  <div class="check-icon">✅</div>
  <h1 class="mt-3 mb-2 fw-bold" style="font-size:1.6rem">Anfrage erfolgreich gesendet!</h1>
  <p style="color:#94a3b8">
    Ihre Notfallanfrage wurde in unserem System erfasst.<br>
    Unser Team wird sich schnellstmöglich bei Ihnen melden.
  </p>
  <hr style="border-color:#334155">
  <p style="color:#94a3b8;font-size:.9rem">In äußerst dringenden Fällen rufen Sie uns bitte direkt an:</p>
  <a href="tel:{{ site_settings.phone_1_number|default:'+4915234209056' }}" class="phone-link">📞 {{ site_settings.phone_1_number|default:'+49 15 234 209 056' }}</a>
  <p style="color:#64748b;font-size:.8rem;margin-top:.5rem">24/7 Notdienst</p>
  <a href="/" class="btn-back">← Zurück zur Startseite</a>
</div>
</body>
</html>
"""
with open(HVALA_HTML, 'w', encoding='utf-8') as f:
    f.write(hvala_html_content)

os.system("supervisorctl restart fina-connect")
print("✅ SOS MODUL JE SREĐEN! Sve je na njemačkom, broj vuče iz baze, i dodan je birač jezika.")
