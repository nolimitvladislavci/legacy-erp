# CC TASK — ARHIVA-1: MOBILE SCAN PORTAL
**Executor: CC Code | Koordinator: Sonnet | Kreiran: 2026-04-14**

---

## CILJ
Komitent dobije link → otvori na mobitelu → slika račun → završi u arhivi Konjika.
Bez logina. Bez instalacije. Bez registracije. Jedan gumb.

## PRAVILA (obavezno pročitati)
- Čitaj FENIX_STATUS.md → sekcija ARHIVA-1 za spec
- Čitaj CC_PLAN_ARHIVA_KOMITENT_KAMERA.md za dijagnozu postojećih bugova
- Pravilo 1: globalni fix, ne lokalna zakrpa
- Pravilo 7: nova ruta /scan/{token}/ → RouteRegistry → AccessLevel.PUBLIC
- Pravilo 5: imports na vrhu, ne conditional
- `manage.py check` mora proći na kraju
- NE diraj gunicorn

---

## ZADACI — REDOSLIJED

### A-1.1 — ScanToken model
Lokacija: `documents/models.py` (dodaj na kraj, uz ArhivaEntry)

```python
class ScanToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='scan_tokens')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    label = models.CharField(max_length=100, blank=True)  # npr. "Gašić Ivan — gorivo"
    expires_at = models.DateTimeField(null=True, blank=True)  # NULL = ne istječe
    max_uses = models.IntegerField(default=0)  # 0 = neograničeno
    use_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False
        return True
    
    def __str__(self):
        return f"{self.company.name} — {self.label or str(self.token)[:8]}"
```

Migracija: `manage.py makemigrations documents && manage.py migrate`

### A-1.2 — View: /scan/{token}/
Dodaj u `documents/views_arhiva.py`:

```
GET /scan/{token}/
  - Ako token ne postoji ili nije valid → lijepa error stranica ("Link nije valjan")
  - Ako valid → prikaži mobile kamera sučelje
  
POST /scan/{token}/
  - Primi file (slika ili PDF)
  - store_document(file_bytes, filename, company_id=token.company_id, ...)
  - Kreiraj ArhivaEntry(company=token.company, source_type='expense', 
      content_category='mobile_scan', session_key=f'scan_token_{token.pk}',
      archived_by=token.created_by)
  - token.use_count += 1; token.save(update_fields=['use_count'])
  - Trigeraj AI OCR async (generate_ai_proposal.apply_async)
  - Vrati JSON: {"ok": true, "message": "Arhivirano ✓", "entry_id": entry.pk}
    ili redirect na success page ako nije AJAX
```

### A-1.3 — URL routing
`documents/urls.py` — dodaj:
```python
path("scan/<uuid:token>/", views.scan_token_upload, name="scan_token_upload"),
```

`permissions/route_registry.py` — dodaj scan_token_upload kao PUBLIC.
Provjeri: RouteRegistry.is_public() mora vratiti True za /hr/documents/scan/*/

### A-1.4 — Mobile UI template
Lokacija: `templates/documents/scan_token_upload.html`

Zahtjevi:
- Cijeli ekran, bijela pozadina, bez navigacije, bez sidebara
- Logo komitenta ili Konjik logo (mali, gore)
- Naziv firme kojoj se arhivira (token.company.name)
- JEDAN veliki gumb: "📸 Slika račun" (visina 80px, zlatna #C9A84C, pun ekran)
  → `<input type="file" accept="image/*,application/pdf" capture="environment">`
  → iOS fix: NE staviti `multiple` s `capture` zajedno (vidi CC_PLAN_ARHIVA_KOMITENT_KAMERA.md)
- Nakon slike: spinner "Arhiviranje..."
- Nakon uspjeha: zelena checkmark + "Arhivirano ✓" + iznos i dobavljač ako OCR brz
- "Pošalji još jedan" link
- Minimalni CSS, system-ui font, font-size: 1.4rem minimum

### A-1.5 — Token generator u knjigov. panelu
Lokacija: umbrella dashboard ili documents dashboard za Konjik admin

Što treba:
- Forma: odaberi komitenta (dropdown s umbrella children) + label (opcionalno) + expiry (opcionalno)
- Submit → kreira ScanToken → prikaže link + QR kod za token
- QR kod: `/qr/?data={full_url}` (Pravilo 6)
- Prikaz: kopirni link + WhatsApp share button (wa.me/?text=...)
- Lista aktivnih tokena za tu firmu (datum, uses, label)

### A-1.6 — Test
Napiši pytest test u `documents/tests/test_scan_token.py`:
```
test_scan_token_valid_upload()     — happy path, slika → ArhivaEntry kreiran
test_scan_token_expired()          — token istekao → 200 s error porukom
test_scan_token_invalid()          — krivi UUID → 404 ili error
test_scan_token_public_route()     — bez logina mora raditi
test_scan_token_use_count()        — use_count se povećava
```

### A-1.7 — Commit i izvještaj
Commitaj sve: `git add -A && git commit -m "ARHIVA-1: ScanToken model + mobile scan portal"`
Na kraju ispiši:
```
ARHIVA-1 STATUS:
  ScanToken model:     ✅/❌
  /scan/{token}/ view: ✅/❌
  Mobile UI:           ✅/❌
  RouteRegistry:       ✅/❌
  Token generator:     ✅/❌
  Tests:               N/N passed
  Commit:              {hash}
```

Ažuriraj FENIX_STATUS.md → GORIVO tablica → ARHIVA-1: status + postotak.

---

## ODMAH NAKON ARHIVA-1 — ARHIVA-2 (isti sprint ako ima vremena)

### A-2 — Magic Link za komitente (kratko)
Lokacija: `core/templates/companies/umbrella_dashboard.html` + view

Što treba:
- Za svakog umbrella child koji NEMA aktivnog usera s emailom:
  Gumb "Pošalji pozivnicu" → kreira magic token → šalje email (ili prikaže link za WhatsApp)
- Za komitente koji imaju email iz Synesisa (core_userprofile ili company.email) — prefill
- Poruka: "Konjik računovodstvo vas poziva da pogledate svoju digitalnu arhivu."
- Nakon klika: welcome stranica s brojem dokumenata u arhivi za tu firmu

---

## KONTEKST
```
Beta firma: Konjik d.o.o. (id: 52e2e048-fd94-401e-8259-fd0cb245f24c)
Marija: marija.brtan (company_admin, totp_enabled=True)
Umbrella children: 75
Arhiva dokumenti: 5.874 (56/75 aktivan)
OCR: radi (100% na gorivo računima)
Korak koji ovo otključava: Korak 11 Beta + Arhiva HR-DE plan
Prioritet: KRITIČAN — Marija testira sutra
```
