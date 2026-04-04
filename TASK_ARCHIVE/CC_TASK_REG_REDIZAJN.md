CC TASK: REGISTRACIJA REDIZAJN — GLOBALNE KOMPONENTE
Datum: 04.04.2026. | Rok: 08.04.2026.
Prioritet: VISOK — prvi kontakt s korisnikom

PRAVILO: Sve komponente REUSAJ iz globalnog sustava — ne pisati ispocetka.
PRAVILO: base.html NE DIRAS. Registracija ima vlastiti base_reg.html.
PRAVILO: READ svaki fajl PRIJE pisanja.
PRAVILO: check 2>&1 | tail -3 nakon svake promjene.

---

KORAK 1: Provjeri teren

EXEC: ls /var/www/fina-connect/static/js/ | grep -iE "fenix|qr|html5"
EXEC: ls /var/www/fina-connect/static/css/
EXEC: grep -n "toggleTheme\|theme-toggle\|fina-theme" /var/www/fina-connect/static/js/fenix-ui.js | head -10
EXEC: grep -n "toggleTheme\|fina-theme" /var/www/fina-connect/static/js/pos/core.js 2>/dev/null | head -5

Zapamti: gdje je toggleTheme() definiran? (core.js, fenix-ui.js ili base.html inline)

---

KORAK 2: base_reg.html — kompletan refaktor

READ: /var/www/fina-connect/templates/registration/base_reg.html (CIJELI)
READ: /var/www/fina-connect/static/css/global_themes.css (prvih 80 linija — CSS varijable)

Modificiraj base_reg.html:

2A) Na vrh <head> dodaj ODMAH ISPOD <meta viewport>:
  {% load static %}

2B) Zamijeni inline :root CSS varijable s:
  <link rel="stylesheet" href="{% static 'css/global_themes.css' %}">
  <link rel="stylesheet" href="{% static 'css/fenix-ui.css' %}">

2C) Zadrzi inline CSS za registraciju-specificne klase (.reg-header, .reg-card, itd.)
    ali provjeri koje varijable vec postoje u global_themes.css i koristi ih.
    Mapping:
      --black        → var(--dark, #0d0d0d) ili --bg iz themes
      --card         → var(--card) iz themes
      --border       → var(--border) iz themes
      --gold         → var(--primary-color) iz themes (to je gold)
      --text         → var(--text-color) iz themes
      --muted        → var(--muted) ili --text-secondary iz themes
      --error        → var(--error-color) iz themes
      --success      → var(--success-color) iz themes

    Ako varijable imaju razlicita imena, dodaj alias na vrh inline <style>:
    :root { --gold: var(--primary-color); --text: var(--text-color); }

2D) Logo: zamijeni "FINA-Connect" s "LIMIT Connect":
    STARO: FINA<span>-Connect</span>
    NOVO:  LIMIT<span> Connect</span>

2E) Dark/Light toggle gumb — dodaj u .reg-header (desni stupac, uz language picker):
    READ: kako je theme toggle implementiran u base.html (linija 234+)
    Kopiraj isti gumb i logiku u base_reg.html header.
    Ukljuci JS za toggle — provjeri je li toggleTheme() u fenix-ui.js ili core.js:
      EXEC: grep -n "function toggleTheme\|toggleTheme" /var/www/fina-connect/static/js/fenix-ui.js | head -5
    Ako je u fenix-ui.js: dodaj <script src="{% static 'js/fenix-ui.js' %}"></script>
    Ako nije: kopiraj inline:
      function toggleTheme() {
        var cur = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('fina-theme', next);
        document.getElementById('theme-icon').className = next === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
      }
      (function(){ var t=localStorage.getItem('fina-theme'); if(t) document.documentElement.setAttribute('data-theme',t); })();

2F) Ukljuci globalne JS fajlove PRIJE </body>:
    <script src="{% static 'js/fenix-camera.js' %}"></script>
    <script src="{% static 'js/html5-qrcode.min.js' %}"></script>
    <script src="{% static 'js/fenix-scan.js' %}"></script>
    <script src="{% static 'js/fenix-permissions.js' %}"></script>

2G) Dodaj FontAwesome ako nije ucitan (provjeri ima li ga vec):
    EXEC: grep -n "fontawesome\|fa-moon\|font-awesome" /var/www/fina-connect/templates/registration/base_reg.html | head -5
    Ako nema: dodaj CDN link u <head>

---

KORAK 3: step1.html — personalizacija s pet parametrom

READ: /var/www/fina-connect/templates/registration/step1.html (CIJELI)
READ: /var/www/fina-connect/registration/views.py (funkcija register_step1 — provjeri context)

3A) U register_step1 view, dodaj u context:
    'pet_name': request.GET.get('pet', '') ili request.session.get('memio_pet', '')
    Spremi u session: request.session['memio_pet'] = pet_name (ako postoji)

3B) U step1.html, ISPOD glavnog h1 naslova, dodaj uvjetni banner:
    Ako pet_name postoji u contextu:
      <div class="pet-welcome-banner">
        <span class="pet-paw">🐾</span>
        <div>
          <strong>{{ pet_name }}</strong> zasluzuje digitalni identitet.
          <span class="pet-sub">Kreiraj profil — besplatno, za 30 sekundi.</span>
        </div>
      </div>

    CSS za banner:
      .pet-welcome-banner {
        display: flex; align-items: center; gap: 16px;
        background: rgba(201,168,76,.08); border: 1px solid rgba(201,168,76,.25);
        border-radius: 10px; padding: 16px 20px; margin-bottom: 24px;
        font-size: .95rem; color: var(--text, #e8e8e8);
      }
      .pet-paw { font-size: 2rem; }
      .pet-sub { display: block; font-size: .78rem; color: var(--muted, #888); margin-top: 2px; }

3C) Promijeni step indikator iz 4 koraka u 2:
    STARO: Plan → Tvrtka → Racun → Potvrda
    NOVO:  Plan → Postavljanje
    Makni nepotrebne .step-line i .step-item.

---

KORAK 4: step2_quick.html — mikrofon + kamera

READ: /var/www/fina-connect/templates/registration/step2_quick.html (CIJELI)

4A) Mikrofon — za unos imena:
    IZNAD polja "Vase ime", dodaj mikrofon gumb:
      <div style="display:flex;gap:8px;align-items:flex-end;margin-bottom:1.2rem">
        <div style="flex:1">
          <label ...>Vase ime *</label>
          <input type="text" name="first_name" id="nameInput" ...>
        </div>
        <button type="button" id="micBtn" onclick="startVoice()"
                title="Izgovori ime"
                style="background:var(--card,#1a1a1a);border:1.5px solid var(--border,#2a2a2a);
                       border-radius:8px;padding:.75rem 1rem;cursor:pointer;
                       color:var(--muted,#888);font-size:1.1rem;transition:all .2s;
                       min-height:48px;min-width:48px">
          🎤
        </button>
      </div>

    JS za mikrofon (dodaj u <script> blok na dnu):
      var _recog = null;
      function startVoice() {
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        var btn = document.getElementById('micBtn');
        if (!SR) { return; }
        if (_recog) { _recog.stop(); _recog = null; btn.textContent = '🎤'; return; }
        _recog = new SR();
        _recog.lang = 'hr-HR';
        _recog.maxAlternatives = 1;
        btn.textContent = '🔴';
        btn.style.borderColor = '#e05252';
        _recog.onresult = function(e) {
          var said = e.results[0][0].transcript;
          var inp = document.getElementById('nameInput');
          if (inp) { inp.value = said; inp.focus(); }
          btn.textContent = '🎤'; btn.style.borderColor = '';
          _recog = null;
        };
        _recog.onerror = _recog.onend = function() {
          btn.textContent = '🎤'; btn.style.borderColor = ''; _recog = null;
        };
        _recog.start();
      }

4B) Email prefill iz sessionStorage (memio integracija):
    U <script> blok na dnu, dodaj:
      document.addEventListener('DOMContentLoaded', function() {
        var savedEmail = '';
        try { savedEmail = sessionStorage.getItem('memio_email') || ''; } catch(e){}
        var emailInp = document.querySelector('[name=email]');
        if (emailInp && !emailInp.value && savedEmail) {
          emailInp.value = savedEmail;
          sessionStorage.removeItem('memio_email');
        }
        // Pet ime iz sessiona
        var petName = '{{ request.session.memio_pet|default:""|escapejs }}';
        if (petName) {
          var nameInp = document.getElementById('nameInput');
          // Fokusiraj email ako je ime vec postavljeno kroz mikrofon
        }
      });

4C) Predlozak fakture preview (opcionalno — ako ima mjesta):
    Dodaj sklopivi panel ISPOD submit gumba:
      <details style="margin-top:1.5rem;border:1px solid var(--border,#2a2a2a);border-radius:8px;padding:0">
        <summary style="padding:12px 16px;cursor:pointer;font-size:.85rem;color:var(--muted,#888);list-style:none">
          ▸ Pogledaj kako izgledaju tvoji racuni
        </summary>
        <div style="padding:16px;display:flex;gap:12px;flex-wrap:wrap">
          <a href="/invoicing/preview/modern/" target="_blank"
             style="padding:8px 16px;border:1px solid var(--border,#2a2a2a);border-radius:6px;
                    color:var(--muted,#888);font-size:.8rem;text-decoration:none;transition:all .2s"
             onmouseover="this.style.borderColor='var(--gold,#c9a84c)';this.style.color='var(--gold,#c9a84c)'"
             onmouseout="this.style.borderColor='';this.style.color=''">
            📄 Modern (HR)
          </a>
          <a href="/invoicing/preview/datev/" target="_blank" style="...">📄 DATEV (DE)</a>
          <a href="/invoicing/preview/bilingual/" target="_blank" style="...">📄 HR/DE Dvojezicni</a>
        </div>
      </details>
    NAPOMENA: Provjeri postoje li ti preview URL-ovi:
    EXEC: grep -rn "preview.*modern\|preview.*datev\|sample.*invoice" /var/www/fina-connect/invoicing/urls.py | head -5

---

KORAK 5: Prikazivanje predlozaka (ako nema preview URL-a — kreiraj)

Ako /invoicing/preview/modern/ ne postoji:
READ: /var/www/fina-connect/invoicing/views.py (prvih 30 linija)

Dodaj jednostavan view na kraj invoicing/views.py:
def invoice_preview_template(request, template_name):
    template_map = {
        'modern': 'invoicing/invoice_hr_modern.html',
        'datev':  'invoicing/invoice_hr_datev.html',
        'bilingual': 'invoicing/invoice_bilingual.html',
        'de':     'invoicing/invoice_de_modern.html',
    }
    tpl = template_map.get(template_name)
    if not tpl:
        from django.http import Http404
        raise Http404
    demo_context = {
        'invoice': {
            'number': 'R-2026-0001',
            'date_issued': '04.04.2026.',
            'date_due': '19.04.2026.',
            'total': '1.250,00',
            'currency': 'EUR',
        },
        'is_demo': True,
    }
    from django.shortcuts import render
    return render(request, tpl, demo_context)

Dodaj URL u invoicing/urls.py:
path('preview/<str:template_name>/', views.invoice_preview_template, name='invoice_preview'),

---

KORAK 6: Finalna provjera

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -3
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5 && curl -s -o /dev/null -w "HTTP %{http_code}" https://limit-connect.com/hr/register/

Test registracije s pet parametrom:
EXEC: curl -s -o /dev/null -w "HTTP %{http_code}" "https://limit-connect.com/hr/register/?pet=Vucko&source=memio"

EXEC: cd /var/www/fina-connect && git add -A && git commit -m "feat(reg): global komponente na registraciji — theme toggle, FenixCamera, mikrofon, pet personalizacija"

DONE kriterij:
- base_reg.html ucitava global_themes.css i fenix-ui.css
- Logo je LIMIT Connect (ne FINA-Connect)
- Theme toggle radi (dark/light)
- FenixCamera i FenixScan.js ucitani
- step1.html prikazuje pet banner ako URL ima ?pet=
- step2_quick.html ima mikrofon gumb pokraj polja za ime
- Email prefill iz sessionStorage (memio integracija)
- manage.py check: 0 errors
