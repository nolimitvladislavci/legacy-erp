# SONNET_TASK_RENTAL_F3 — UI: Check-in + Bukiranje + Marija
## Agent: Sonnet | Prioritet: P1

---

## 4 EKRANA KOJE GRADIŠ

### EKRAN 1 — Check-in flow (iznajmljivač/Marija)

```
┌────────────────────────────────────────────────────┐
│  ← Rezervacije     Check-in: Apartman Sunset       │
│                                                    │
│  Rezervacija: KO-00042                             │
│  Datum: 24.3.2026 → 28.3.2026 (4 noći)            │
│                                                    │
│  GOSTI (1/2 prijavljeno)                           │
│  ┌──────────────────────────────────────────────┐  │
│  │ ✅ Ivan Brtan        HR          HRV         │  │
│  │    Putovnica AB123456                        │  │
│  │                                              │  │
│  │ ⏳ [Dodaj 2. gosta]                          │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  [  📷 Slici dokument  ]  [  ✍️ Unesi ručno  ]    │
│                                                    │
│  ───────────────────────────────────────────────   │
│                                                    │
│  [  ✅ eVisitor prijava (2 gosta)  ]               │
│  [  🖨️ Ispiši račun (156,80€)  ]                  │
└────────────────────────────────────────────────────┘
```

### EKRAN 2 — OCR forma (nakon slikanja)

```
┌────────────────────────────────────────────────────┐
│  ← Natrag          Novi gost — provjeri podatke    │
│                                                    │
│  ┌──────────────────┐                             │
│  │  [slika dokumenta│  ✅ AI pročitao podatke      │
│  │   thumbnail]     │  Pouzdanost: 96%             │
│  └──────────────────┘                             │
│                                                    │
│  Ime:         [Ivan          ]  ← auto-popunjeno  │
│  Prezime:     [Brtan         ]  ← auto-popunjeno  │
│  Datum rođ.:  [01.01.1991    ]  ← auto-popunjeno  │
│  Dokument:    [AB123456      ]  ← auto-popunjeno  │
│  Drzavljan.:  [Hrvatska      ]  ← auto-popunjeno  │
│  Spol:        [● M  ○ F      ]                    │
│                                                    │
│  [ Prihvati i prijavi ]    [ Ispravi ]             │
└────────────────────────────────────────────────────┘
```

### EKRAN 3 — Gost self-check-in (QR stranica)

```
URL: /hr/rental/guest/{access_qr}/
(Gost skenira QR kod u apartmanu)

┌────────────────────────────────────────────────────┐
│          🏠 Dobrodošli u Apartman Sunset            │
│                                                    │
│  Vaš boravak: 24.3 — 28.3.2026                    │
│  Check-in od: 14:00 | Check-out do: 11:00          │
│                                                    │
│  📶 WiFi: SunsetApt2B  |  Lozinka: Sunset2026!    │
│  🔑 Kod brave: 4821                                │
│                                                    │
│  ─────────────────────────────────────────────     │
│  Za brži check-in unesite podatke sami:            │
│                                                    │
│  Ime i prezime: [________________]                 │
│  Br. putovnice: [________________]                 │
│  Drzavljanstvo: [________________]                 │
│                                                    │
│  Ili: [ 📷 Skeniri putovnicu ]                     │
│                                                    │
│  [ Potvrdi i pošalji ]                             │
│                                                    │
│  🔒 Podaci se koriste isključivo za zakonsku       │
│     prijavu turista. GDPR sukladno.                │
└────────────────────────────────────────────────────┘
```

### EKRAN 4 — Marija dashboard (računovođa)

```
URL: /hr/rental/accountant/
(Marija vidi sve klijente iznajmljivače)

┌────────────────────────────────────────────────────┐
│  Rental klijenti — Konjik d.o.o.                  │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │ Pero Perić · 3 apartmana · Rovinj            │  │
│  │ YTD: 18.240€ (46% praga)  🟡                 │  │
│  │ [Pregled] [TZ-2] [EP evidencija] [Arhiva]    │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │ Ana Kovač · 1 soba · Split                   │  │
│  │ YTD: 37.800€ (95% praga)  🔴 UPOZORENJE      │  │
│  │ [Pregled] [TZ-2] [EP evidencija] [Arhiva]    │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │ Marko Novak · 2 apartmana · Dubrovnik        │  │
│  │ YTD: 8.100€ (20% praga)   🟢                 │  │
│  │ [Pregled] [TZ-2] [EP evidencija] [Arhiva]    │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

---

## TEMPLATES

### `rental/templates/rental/checkin_flow.html`

Extend base.html. Koristi JavaScript za:
1. Webcam/kamera → slika dokumenta → POST na `/rental/booking/{pk}/ocr/`
2. AI vraća JSON → auto-popuni formu
3. Submit forme → kreira Guest objekt
4. "eVisitor prijava" gumb → generira XML za download
5. "Ispiši račun" → PDF u novom tabu

### `rental/templates/rental/guest_self_checkin.html`

**STANDALONE** — ne extend base.html (gost nema login).
- Minimalistički bijeli dizajn
- Logo iz Company settingsa ili default
- Multi-jezik (HR/EN/DE automatski prema Accept-Language)
- Kamera za OCR (isti JS kao check-in flow)
- GDPR consent checkbox (obavezan)
- Nakon slanja → zahvalna stranica s WiFi i lockcode

### `rental/templates/rental/accountant_dashboard.html`

Extend base.html.
- Lista klijenata iznajmljivača
- Progress bar za svaki klijent (% prema 40k pragu)
- Crveni alert za > 90%
- Gumbi: TZ-2 PDF download, EP CSV download, → Arhiva

---

## VIEWS (dodaj u rental/views.py)

```python
def checkin_flow(request, booking_pk):
    """Check-in forma za iznajmljivača."""

def guest_ocr_upload(request, booking_pk):
    """AJAX: prima sliku dokumenta, vraća OCR JSON."""
    # POST: image → haiku_classify → return JSON
    from rental.ocr import extract_mrz_with_haiku
    ...

def evisitor_xml_download(request, booking_pk):
    """Preuzmi eVisitor XML."""
    from rental.evisitor import build_evisitor_xml
    ...

def rental_invoice_pdf(request, booking_pk):
    """PDF računa za gosta."""
    # Koristi invoicing.services.generate_invoice_pdf
    ...

def accountant_dashboard(request):
    """Marija vidi sve klijente iznajmljivače."""
    ...

def tz2_download(request, company_id, year):
    """TZ-2 PDF download za Mariju."""
    from rental.tz2_generator import generate_tz2_pdf
    ...
```

---

## URLS

Dodaj u `rental/urls.py`:

```python
path('booking/<int:pk>/checkin/', views.checkin_flow, name='checkin_flow'),
path('booking/<int:pk>/ocr/', views.guest_ocr_upload, name='guest_ocr'),
path('booking/<int:pk>/evisitor.xml', views.evisitor_xml_download, name='evisitor_xml'),
path('booking/<int:pk>/invoice.pdf', views.rental_invoice_pdf, name='rental_invoice_pdf'),
path('guest/<str:access_qr>/', views.guest_self_checkin, name='guest_self_checkin'),
path('accountant/', views.accountant_dashboard, name='accountant_dashboard'),
path('accountant/<int:company_id>/tz2/<int:year>.pdf', views.tz2_download, name='tz2_download'),
```

---

## DONE kriterij

```
1. curl .../rental/guest/{test_qr}/ → 200, standalone page, bez logina
2. Marija pristupa .../rental/accountant/ → vidi klijente
3. Check-in flow: slika dokumenta → OCR JSON → forma popunjena
4. eVisitor XML: valid XML s gostima
5. Račun PDF: generiran s ispravnim iznosom
```
