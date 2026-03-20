import os
import shutil

UPIT_FILE = '/var/www/fina-connect/burza/templates/burza/public_upit.html'
HVALA_FILE = '/var/www/fina-connect/burza/templates/burza/upit_hvala.html'

# 1. Backup datoteka
if os.path.exists(UPIT_FILE):
    shutil.copy2(UPIT_FILE, UPIT_FILE + '.bak')
if os.path.exists(HVALA_FILE):
    shutil.copy2(HVALA_FILE, HVALA_FILE + '.bak')

# 2. Savršeni Njemački za JAVNU FORMU (public_upit.html)
upit_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Projektanfrage senden – Visković Group</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;600;700&family=Barlow+Condensed:wght@700&family=Cormorant+Garamond:ital,wght@0,300;1,400&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{--black:#0a0a0a;--dark:#111214;--surface:#181a1d;--border:#252830;--muted:#4a5060;--white:#f0ede8;--gold:#c9a84c;--gold2:#e8c96a}
body{background:var(--black);color:var(--white);font-family:'Barlow',sans-serif;font-weight:300;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:40px 20px}
.card{background:var(--surface);border:1px solid var(--border);padding:48px;width:100%;max-width:600px;position:relative}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--gold),transparent)}
.ey{font-family:'Barlow Condensed',sans-serif;font-size:.65rem;letter-spacing:5px;text-transform:uppercase;color:var(--gold);margin-bottom:8px}
.ttl{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:300;color:var(--white);margin-bottom:8px;line-height:1.1}
.ttl em{font-style:italic;color:var(--gold)}
.sub{font-size:.88rem;color:var(--muted);margin-bottom:36px;line-height:1.6}
.fg{margin-bottom:16px}
label{display:block;font-size:.72rem;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
input,select,textarea{width:100%;background:var(--dark);border:1px solid var(--border);padding:13px 16px;color:var(--white);font-family:'Barlow',sans-serif;font-size:.9rem;outline:none;transition:border-color .2s}
input:focus,select:focus,textarea:focus{border-color:var(--gold)}
input::placeholder,textarea::placeholder{color:var(--muted)}
select option{background:var(--dark)}
textarea{resize:vertical;min-height:100px}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.sbtn{width:100%;padding:16px;background:var(--gold);color:var(--black);border:none;font-family:'Barlow Condensed',sans-serif;font-size:.88rem;font-weight:700;letter-spacing:3px;text-transform:uppercase;cursor:pointer;transition:background .2s;margin-top:8px}
.sbtn:hover:not(:disabled){background:var(--gold2)}
.sbtn:disabled{opacity:.6;cursor:not-allowed}
.err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:#fca5a5;padding:14px;font-size:.85rem;margin-bottom:20px}
.sp{width:14px;height:14px;border-radius:50%;border:2px solid rgba(0,0,0,.2);border-top-color:var(--black);animation:spin .7s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}
.div{height:1px;background:var(--border);margin:24px 0}
a.bk{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:.78rem;text-decoration:none;margin-bottom:28px;transition:color .2s}
a.bk:hover{color:var(--gold)}
</style>
</head>
<body>
<div class="card">
<a href="/calculator/" class="bk">← Zurück zum Rechner</a>
<div class="ey">Projektbörse – Visković Group</div>
<h1 class="ttl">Senden Sie uns <em>Ihre</em><br>Projektanfrage.</h1>
<p class="sub">Beschreiben Sie Ihr Projekt. Unser Team prüft die Anfrage und meldet sich innerhalb von 24–48 Stunden bei Ihnen.</p>
{% if error %}<div class="err">❌ {{ error }}</div>{% endif %}
<form method="POST" id="uf">
{% csrf_token %}
<div class="fg"><label>Titel *</label><input type="text" name="title" value="{{ prefill.title }}" placeholder="Z.B. Komplette Badsanierung 8m²" required></div>
<div class="fg"><label>Kategorie *</label><select name="category">{% for v,l in categories %}<option value="{{ v }}">{{ l }}</option>{% endfor %}</select></div>
<div class="fg"><label>Projektbeschreibung *</label><textarea name="description" placeholder="Beschreiben Sie, was gemacht werden soll..." required>{{ prefill.description }}</textarea></div>
<div class="fg"><label>Standort *</label><input type="text" name="location" value="{{ prefill.location }}" placeholder="Stadt, Postleitzahl" required></div>
<div class="row2"><div class="fg"><label>Budget von (€)</label><input type="number" name="budget_from" value="{{ prefill.budget_from }}" placeholder="1000" min="0"></div><div class="fg"><label>Budget bis (€)</label><input type="number" name="budget_to" value="{{ prefill.budget_to }}" placeholder="5000" min="0"></div></div>
<div class="div"></div>
<div class="row2"><div class="fg"><label>Ihr Name *</label><input type="text" name="contact_name" placeholder="Vor- und Nachname" required></div><div class="fg"><label>Telefon *</label><input type="tel" name="contact_phone" placeholder="+49..." required></div></div>
<div class="fg"><label>E-Mail</label><input type="email" name="contact_email" placeholder="email@beispiel.de"></div>
<button type="submit" class="sbtn" id="sb">Anfrage senden →</button>
</form>
</div>
<script>document.getElementById('uf').addEventListener('submit',function(){const b=document.getElementById('sb');b.disabled=true;b.innerHTML='<span class="sp"></span>&nbsp; Wird gesendet...'});</script>
</body></html>
"""

with open(UPIT_FILE, 'w', encoding='utf-8') as f:
    f.write(upit_content)


# 3. Savršeni Njemački za ZAHVALU (upit_hvala.html)
hvala_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Anfrage erhalten – Visković Group</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;600&family=Barlow+Condensed:wght@700&family=Cormorant+Garamond:ital,wght@0,300;1,400&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}:root{--black:#0a0a0a;--dark:#111214;--surface:#181a1d;--border:#252830;--muted:#4a5060;--white:#f0ede8;--gold:#c9a84c}body{background:var(--black);color:var(--white);font-family:'Barlow',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:40px 20px}.card{background:var(--surface);border:1px solid var(--border);padding:60px;max-width:520px;width:100%;text-align:center;position:relative}.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--gold),transparent)}.ey{font-family:'Barlow Condensed',sans-serif;font-size:.65rem;letter-spacing:5px;text-transform:uppercase;color:var(--gold);margin-bottom:8px}.ttl{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:300;color:var(--white);margin-bottom:16px}.ttl em{font-style:italic;color:var(--gold)}p{color:#94a3b8;line-height:1.7;margin-bottom:24px;font-size:.92rem}.steps{text-align:left;background:var(--dark);border:1px solid var(--border);padding:20px;margin:28px 0}.step{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid var(--border);font-size:.85rem;color:#94a3b8}.step:last-child{border-bottom:none}.sn{width:24px;height:24px;background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.3);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;color:var(--gold);flex-shrink:0}a.btn{display:inline-block;padding:13px 32px;background:var(--gold);color:var(--black);font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.85rem;letter-spacing:2px;text-transform:uppercase;text-decoration:none}</style>
</head>
<body><div class="card"><div style="font-size:3rem;margin-bottom:24px">✅</div><div class="ey">Projektbörse</div><h1 class="ttl">Anfrage <em>erhalten.</em></h1><p>Ihre Projektanfrage wurde erfolgreich übermittelt. Wir melden uns innerhalb von 24–48 Stunden bei Ihnen.</p><div class="steps"><div class="step"><div class="sn">1</div><div>Unser Team prüft die Anfrage</div></div><div class="step"><div class="sn">2</div><div>Wenn wir übernehmen – kontaktieren wir Sie direkt</div></div><div class="step"><div class="sn">3</div><div>Falls keine Kapazität frei ist – Angebot an unsere geprüften Partner</div></div></div><a href="/bau/" class="btn">Zurück zur Startseite →</a></div></body></html>
"""

with open(HVALA_FILE, 'w', encoding='utf-8') as f:
    f.write(hvala_content)

os.system("supervisorctl restart fina-connect")
print("✅ BURZA FORMA I ZAHVALA SU PREVEDENE! Server je restartan.")
