# CC Task — Arhiva: upute + promo materijal

## Kontekst
Marija je knjigovođa koja vodi 60+ komitenata.
Arhiva je njen primarni alat. Nema uputa. Nema vodiča.
Cilj: "bakica u 3 klika" — svaki klijent mora moći koristiti bez objašnjenja.

## Zadatak 1 — Javna stranica uputa

Kreiraj: `/var/www/fina-connect/templates/website/arhiva_upute.html`

Standalone HTML (ne extends base.html), dark gold tema, javno dostupno.

Sadržaj:
```
LIMIT Connect — Arhiva dokumenata
"Svi vaši računi na jednom mjestu"

━━━ 3 KORAKA ━━━

KORAK 1 — UPLOAD
[ikona kamere/uploada]
Fotografirajte račun ili povucite PDF.
Podržava: slike, PDF, XML (eRačun)

KORAK 2 — PREPOZNAVANJE  
[ikona AI/magnifier]
Sustav automatski čita:
datum, iznos, partnera, PDV
Sve za manje od 3 sekunde.

KORAK 3 — PRONAĐI KADA TREBAŠ
[ikona tražilice]
Traži po: datum | partner | iznos | tip dokumenta
Export u Excel jednim klikom.
ZOR: čuva 11 godina automatski.

━━━ BONUS ━━━
✅ eRačun automatski prima i arhivira
✅ AI prijedlog knjiženja
✅ Revizijski trag svake promjene
✅ Radi na mobitelu

[Prijavi se] → limit-connect.com
```

Stil: veliki font (min 16px), puno bjeline, ikone FontAwesome,
gold (#c9a84c) za naslove, tamna pozadina (#0a0a0a).
Mobile-first. Printabilno (CSS @media print).

## Zadatak 2 — URL za stranicu

U core/urls.py dodaj (u javni blok bez login_required):
```python
path('arhiva-upute/', 
     lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/arhiva_upute.html'), 
     name='arhiva_upute'),
```

## Zadatak 3 — Onboarding tooltip u arhiva_list.html

Kad korisnik prvi put posjeti arhivu (localStorage flag), prikaži info bar:
```html
<div id="arhiva-intro" style="display:none; background:#1a2e1a; border:1px solid #22c55e; 
     border-radius:8px; padding:.75rem 1rem; margin-bottom:1rem; font-size:.85rem;">
  <span style="color:#22c55e; font-weight:700;">📂 Dobrodošli u Arhivu</span>
  — Upload dokumenta: gumb gore desno. Traži: polje za pretragu. 
  Export u Excel: gumb "Export".
  <button onclick="document.getElementById('arhiva-intro').style.display='none'; 
                   localStorage.setItem('arhiva_intro_seen','1')" 
          style="float:right; background:none; border:none; color:#888; cursor:pointer;">✕</button>
</div>
<script>
if (!localStorage.getItem('arhiva_intro_seen')) {
    document.getElementById('arhiva-intro').style.display = 'block';
}
</script>
```

Dodaj odmah ispod `<div class="container">` ili prvog main wrappera u arhiva_list.html.

## Provjera
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -2
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/arhiva-upute/
# Mora biti 200 (javna stranica, bez logina)
```

## PRAVILA
- arhiva_upute.html je STANDALONE — bez extends, bez login_required
- Čitaj arhiva_list.html CIJELI prije dodavanja intro bara
- Backup: arhiva_list.html.bak
- Django check 0 issues
