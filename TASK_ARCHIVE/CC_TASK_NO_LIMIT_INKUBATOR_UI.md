# CC_TASK: NO LIMIT PORTAL — Inkluzija + Ambasador UI
# Datum: 04.04.2026. | Rok: 06.04.2026. | Prioritet: P1
# Nadogradnja: templates/website/no_limit.html (1213 linija)

PRAVILO: READ template PRVO. base.html, .env NE DIRAS.

## KORAK 1 — PROVJERI
```bash
wc -l templates/website/no_limit.html
grep -n "SEKCIJA\|<!-- " templates/website/no_limit.html | head -30
grep -n "inkubator\|invalid\|ambasador\|ambassador" templates/website/no_limit.html | head -10
grep -n "def no_limit" website/views.py | head -5
grep -n "no.limit\|no_limit" core/urls.py | head -5
```

## KORAK 2 — DODAJ 3 NOVE SEKCIJE (na kraj, prije footera)

READ: zadnjih 100 linija templates/website/no_limit.html — pronađi gdje je footer/kraj.

DODAJ ove 3 sekcije ISPRED footera:

### SEKCIJA A — INKUBATOR: Ambasador programa
```html
<!-- NO LIMIT INKUBATOR — Ambasador programa -->
<section id="inkubator" style="padding:5rem 1.5rem;background:var(--dark,#0d0f11);">
<div style="max-width:1000px;margin:0 auto;">

  <div style="text-align:center;margin-bottom:3rem;">
    <div style="display:inline-block;padding:.4rem 1rem;background:rgba(201,168,76,.1);
      border:1px solid rgba(201,168,76,.3);border-radius:99px;
      font-size:.78rem;color:var(--gold,#c9a84c);margin-bottom:1rem;letter-spacing:.1em;">
      NO LIMIT INKUBATOR
    </div>
    <h2 style="font-size:clamp(1.75rem,4vw,2.75rem);font-weight:800;margin-bottom:.75rem;">
      Digitalno zapošljavanje.<br>
      <span style="color:var(--gold,#c9a84c);">Bez prepreka.</span>
    </h2>
    <p style="color:#94a3b8;max-width:560px;margin:0 auto;font-size:1rem;">
      NO LIMIT udruga otvara vrata digitalnog rada osobama s invaliditetom.
      Postanite Ambasador ili Mini-Računovođa — od kuće, vlastitim tempom.
    </p>
  </div>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem;">

    <!-- Kartica 1 -->
    <div style="background:#181a1d;border:1px solid rgba(201,168,76,.2);border-radius:14px;padding:2rem;">
      <div style="font-size:2.5rem;margin-bottom:1rem;">📲</div>
      <h3 style="font-size:1.15rem;font-weight:700;margin-bottom:.5rem;">Postanite Ambasador</h3>
      <p style="color:#94a3b8;font-size:.88rem;margin-bottom:1.25rem;line-height:1.6;">
        Preporučujte LIMIT Connect u svom gradu. Svaki aktivni klijent
        donosi vam <strong style="color:var(--gold);">15% trajne komisije</strong>.
        Vlastiti link, QR kod, AI podrška.
      </p>
      <div style="font-size:.8rem;color:#64748b;margin-bottom:1rem;">
        ✓ Rad od doma &nbsp;✓ Bez tehničkog znanja &nbsp;✓ Puna podrška
      </div>
      <a href="#prijava-ambasador" style="display:block;text-align:center;
        padding:.75rem;background:var(--gold,#c9a84c);color:#000;
        font-weight:700;border-radius:8px;font-size:.9rem;">
        Prijavi se →
      </a>
    </div>

    <!-- Kartica 2 -->
    <div style="background:#181a1d;border:1px solid rgba(201,168,76,.2);border-radius:14px;padding:2rem;">
      <div style="font-size:2.5rem;margin-bottom:1rem;">📊</div>
      <h3 style="font-size:1.15rem;font-weight:700;margin-bottom:.5rem;">Postanite Mini-Računovođa</h3>
      <p style="color:#94a3b8;font-size:.88rem;margin-bottom:1.25rem;line-height:1.6;">
        Naučite proknjižavati račune uz AI asistenta. Radite za stvarne
        klijente, zarađujte po ugovoru o djelu.
        Mentor: <strong style="color:var(--gold);">Marija Brtan, ovl. računovođa</strong>.
      </p>
      <div style="font-size:.8rem;color:#64748b;margin-bottom:1rem;">
        ✓ Online edukacija &nbsp;✓ Certifikat &nbsp;✓ HZZ sufinanciranje
      </div>
      <a href="#prijava-racunovodja" style="display:block;text-align:center;
        padding:.75rem;background:transparent;color:var(--gold);
        border:1.5px solid var(--gold);font-weight:700;border-radius:8px;font-size:.9rem;">
        Više informacija →
      </a>
    </div>

    <!-- Kartica 3 -->
    <div style="background:#181a1d;border:1px solid rgba(201,168,76,.2);border-radius:14px;padding:2rem;">
      <div style="font-size:2.5rem;margin-bottom:1rem;">🐾</div>
      <h3 style="font-size:1.15rem;font-weight:700;margin-bottom:.5rem;">Pet Hotel — Socijalno poduzetništvo</h3>
      <p style="color:#94a3b8;font-size:.88rem;margin-bottom:1.25rem;line-height:1.6;">
        NO LIMIT udruga razvija pet hotel koji zapošljava osobe s
        invaliditetom. Terapeutski rad s životinjama.
        EU LEADER fond sufinancira do <strong style="color:var(--gold);">85%</strong>.
      </p>
      <div style="font-size:.8rem;color:#64748b;margin-bottom:1rem;">
        ✓ Fizički rad &nbsp;✓ Terapija &nbsp;✓ Zajednička zadruga
      </div>
      <a href="#pet-hotel-inkubator" style="display:block;text-align:center;
        padding:.75rem;background:transparent;color:#94a3b8;
        border:1.5px solid #334155;font-weight:600;border-radius:8px;font-size:.9rem;">
        Uskoro →
      </a>
    </div>

  </div>
</div>
</section>

<!-- PRIJAVA FORMA — Ambasador -->
<section id="prijava-ambasador" style="padding:4rem 1.5rem;background:#111214;">
<div style="max-width:600px;margin:0 auto;">
  <h2 style="font-size:1.5rem;font-weight:800;text-align:center;margin-bottom:.5rem;">
    Prijava za Ambasadora
  </h2>
  <p style="color:#94a3b8;text-align:center;margin-bottom:2rem;font-size:.88rem;">
    Popunite kratku prijavu. Kontaktiramo vas u roku 48h.
  </p>
  <form method="post" action="/hr/no-limit/ambasador-prijava/"
    style="background:#181a1d;border:1px solid #252830;border-radius:14px;padding:2rem;">
    {% csrf_token %}
    <div style="display:grid;gap:1rem;">
      <div>
        <label style="display:block;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:.35rem;">Ime i prezime *</label>
        <input name="ime_prezime" required style="width:100%;background:#0d0f11;border:1px solid #252830;border-radius:8px;padding:.65rem .875rem;color:#e2e8f0;font-size:.9rem;">
      </div>
      <div>
        <label style="display:block;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:.35rem;">Email *</label>
        <input name="email" type="email" required style="width:100%;background:#0d0f11;border:1px solid #252830;border-radius:8px;padding:.65rem .875rem;color:#e2e8f0;font-size:.9rem;">
      </div>
      <div>
        <label style="display:block;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:.35rem;">Grad</label>
        <input name="grad" style="width:100%;background:#0d0f11;border:1px solid #252830;border-radius:8px;padding:.65rem .875rem;color:#e2e8f0;font-size:.9rem;" placeholder="npr. Osijek">
      </div>
      <div>
        <label style="display:block;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:.35rem;">Kratko o sebi</label>
        <textarea name="o_sebi" rows="3" style="width:100%;background:#0d0f11;border:1px solid #252830;border-radius:8px;padding:.65rem .875rem;color:#e2e8f0;font-size:.9rem;resize:vertical;" placeholder="Što vas motivira da postanete Ambasador?"></textarea>
      </div>
      <button type="submit" style="background:var(--gold,#c9a84c);color:#000;font-weight:700;border:none;border-radius:8px;padding:.875rem;font-size:1rem;cursor:pointer;">
        Pošalji prijavu →
      </button>
    </div>
    <p style="color:#475569;font-size:.75rem;text-align:center;margin-top:1rem;">
      Vaši podaci koriste se isključivo za kontakt. GDPR usklađeno.
    </p>
  </form>
</div>
</section>
```

## KORAK 3 — VIEW za prijavu ambasadora

READ: website/views.py ili no_limit/views.py — pronađi gdje idu no_limit views.

DODAJ:
```python
@require_POST
def ambasador_prijava(request):
    """Prima prijavu za NO LIMIT Ambasador program."""
    ime     = request.POST.get('ime_prezime','').strip()
    email   = request.POST.get('email','').strip()
    grad    = request.POST.get('grad','').strip()
    o_sebi  = request.POST.get('o_sebi','').strip()

    if not ime or not email:
        messages.error(request, 'Ime i email su obavezni.')
        return redirect('/no-limit/#prijava-ambasador')

    # WhatsApp Ivan
    try:
        from notifications.whatsapp import send_whatsapp
        send_whatsapp(
            to='+4915771998747',
            message=f'🌟 NO LIMIT Ambasador prijava!\n'
                    f'Ime: {ime}\nEmail: {email}\nGrad: {grad}\n'
                    f'O sebi: {o_sebi[:200]}'
        )
    except Exception:
        pass

    messages.success(request, 'Prijava primljena! Kontaktiramo vas u roku 48h.')
    return redirect('/no-limit/#prijava-ambasador')
```

URL dodati u no_limit/urls.py ili core/urls.py:
```python
path('no-limit/ambasador-prijava/', views.ambasador_prijava, name='no_limit_ambasador_prijava'),
```

## KORAK 4 — VERIFY + COMMIT
```bash
venv/bin/python manage.py check 2>&1 | tail -3
systemctl restart gunicorn-fina && sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/no-limit/
git add -A && git commit -m "feat(no-limit): Inkubator UI — ambasador, računovođa, pet hotel sekcije"
```

DONE: [ ] 3 sekcije dodane [ ] Prijava forma radi [ ] WhatsApp notifikacija [ ] View + URL
