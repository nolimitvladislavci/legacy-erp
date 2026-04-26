# CC TASK — ARHIVA 13/10 FINALIZACIJA
**Kreiran: 2026-04-26 | Prioritet: KRITIČAN — prezentacija ujutro**
**Executor: CC Code | Koordinator: Sonnet**

---

## KONTEKST

Arhiva modul je na 9.5/10. Sve funkcionira. Dva preostala detalja do 13/10.

Nije potrebno čitati sve fajlove iznova — sve je implementirano.
Čitaj samo ono navedeno u svakom zadatku.

---

## ZADATAK 1 — Sintaksna greška u _umbrella_table.html

**Fajl:** `templates/dashboards/_umbrella_table.html`
**Linija:** 83-84

Gumb za "Odvezi" ima `<button` bez zatvarajućeg `>` na atributima:

```html
<!-- BROKEN: -->
<button type="submit" class="u-unlink-btn" title="{% trans 'Odvezi' %}"
        onclick="return confirm('Odvezati {{ cd.company.name }}?')"
  <i class="fas fa-unlink"></i>
</button>

<!-- FIX: dodati > na kraju onclick reda: -->
<button type="submit" class="u-unlink-btn" title="{% trans 'Odvezi' %}"
        onclick="return confirm('Odvezati {{ cd.company.name }}?')">
  <i class="fas fa-unlink"></i>
</button>
```

Napravi fix, ništa drugo ne diraj u fajlu.

---

## ZADATAK 2 — Kategorija selector u scan_mobile.html

**Fajl:** `templates/documents/scan_mobile.html`
**Kontekst:** View već šalje `categories` u context (vidi views_scan.py:80-86). Template ih nije prikazivao.

Dodaj **kategorija selector** u scan mobile UI. Ubaci nakon div-a koji prikazuje naziv firme / label, a PRIJE upload gumba.

Zahtjevi:
- Horizontalni scroll chips (ne dropdown!) — brži na mobitelu
- Ikona + naziv HR kategorije po chipu
- Defaultno nema selektiranog čipa (AI auto-detektira)
- Klik na chip → `data-selected` toggle, vizualni highlight (zlatna boja)
- Selektirana vrijednost (`code`) ide kao hidden field `category_code` u POST

Primjer HTML strukture (adaptiraj u stil scan_mobile.html koji već postoji):
```html
{% if categories %}
<div class="cat-scroll" style="overflow-x:auto;white-space:nowrap;margin:12px 0;padding:4px 0">
  {% for cat in categories %}
  <button type="button" class="cat-chip" data-code="{{ cat.code }}"
          onclick="selectCat(this)"
          style="display:inline-flex;align-items:center;gap:5px;margin-right:6px;
                 padding:7px 14px;border-radius:20px;border:1px solid #333;
                 background:#1a1a1a;color:#aaa;font-size:.8rem;cursor:pointer;
                 white-space:nowrap;transition:all .15s">
    {{ cat.name_hr }}
  </button>
  {% endfor %}
</div>
<input type="hidden" name="category_code" id="categoryCode" value="">
{% endif %}

<script>
function selectCat(btn){
  document.querySelectorAll('.cat-chip').forEach(function(b){
    b.style.background='#1a1a1a';b.style.color='#aaa';b.style.borderColor='#333';
  });
  var code = btn.dataset.code;
  var current = document.getElementById('categoryCode').value;
  if(current === code){
    document.getElementById('categoryCode').value='';
  } else {
    btn.style.background='rgba(201,168,76,.15)';
    btn.style.color='#C9A84C';
    btn.style.borderColor='#C9A84C';
    document.getElementById('categoryCode').value=code;
  }
}
</script>
```

Provjeri da `category_code` value se šalje u FormData pri upload-u. Pogledaj kako POST radi u scan_mobile.html — ako šalje FormData ručno, dodaj:
```javascript
fd.append('category_code', document.getElementById('categoryCode').value);
```

---

## ZADATAK 3 — Fenix V3 link u umbrella tablici

**Fajl:** `templates/dashboards/_umbrella_table.html`
**Gdje:** u `.div` s action gumbima (linija ~72, između scan i share gumba)

Dodaj gumb koji otvara Fenix V3 mobilni upload za tog komitenta:

```html
<a href="https://limit-connect.com/hr/arhiva/mobile/?company={{ cd.company.pk }}"
   target="_blank"
   class="u-action-btn" title="Fenix V3 Upload — {{ cd.company.name }}"
   style="font-size:10px;font-weight:700;color:#a78bfa;">
  V3
</a>
```

CSS hover (dodaj u `<style>` blok koji već postoji):
```css
.u-action-v3:hover{background:rgba(167,139,250,.1);color:#a78bfa;border-color:#a78bfa;}
```

Dodaj class `u-action-v3` na gumb.

---

## ZADATAK 4 — manage.py check + gunicorn reload

Nakon sva 3 zadatka:

```bash
cd /var/www/fina-connect
/var/www/fina-connect/venv/bin/python manage.py check
# Mora biti: System check identified no issues (0 silenced).

sudo systemctl reload gunicorn-fina
```

Verify live:
```bash
curl -s -o /dev/null -w "%{http_code}" https://limit-connect.com/hr/scan/405dfc43-074f-429a-a0a7-5e965f26e04b/
# Mora biti 200
```

---

## ZAVRŠNI IZVJEŠTAJ

Na kraju ispiši:

```
ARHIVA 13/10 STATUS:
  T1 _umbrella_table sintaksna greška:   ✅/❌
  T2 Kategorija selector scan_mobile:    ✅/❌
  T3 Fenix V3 link u tablici:            ✅/❌
  T4 manage.py check:                    ✅/❌ (N silenced)
  T4 gunicorn reload:                    ✅/❌
  Scan URL live test:                    HTTP XXX
  Commit:                                {hash}
```

Ažuriraj FENIX_STATUS.md — dodaj sesiju s gornjim izvještajem i "Zadnje azuriranje: 2026-04-26".

---

## DEMO URL-OVI (za info, ne diraj)

- Scan upload (komitent): https://limit-connect.com/hr/scan/405dfc43-074f-429a-a0a7-5e965f26e04b/
- Arhiva portal (komitent): https://limit-connect.com/hr/arhiva-portal/ba44e502-eb67-4f62-a490-b03c4bfdb3fb/
- Umbrella panel (Marija): https://limit-connect.com/hr/dashboard/umbrella/
- Fenix V3 mobile: https://limit-connect.com/hr/arhiva/mobile/
