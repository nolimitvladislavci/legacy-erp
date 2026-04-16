# CC TASK — STOLARIJA VOICE V2 + BUG FIXES
> Kreirao: Sonnet | Datum: 2026-04-16
> Prioritet: HIGH — Zdenko Šoš pilot korisnik testirao, ocijenio: "dobro za kod kuće, za gradilište nije"

---

## STATUS PRETHODNIH BUGOVA (provjeri prije nastavka)

### ✅ RIJEŠENO (Sonnet, b297a85d):
- Mikrofon: dodan onerror/onnomatch/isListening auto-restart
- Dimenzije linkabilne: measure.html + offer_detail.html
- Offer responsive: table-responsive + overflow-x:auto

### ❌ JOŠ OTVORENO — ti trebaš riješiti:

**BUG-1: Ponuda se ne otvara**
- URL: `/hr/stolarija/ponuda/<offer_id>/`
- View: `stolarija/views.py:341 offer_detail()`
- Sumnja: WindowOffer query ili SVG generacija baca exception
- Koraci: dodaj try/except oko svg_window import + logger.exception u offer_detail

**BUG-2: Stranica se sakrila desno (Joker panel)**
- base.html Joker panel ili right panel uzrokuje overflow
- Provjeri: `stolarija/templates/stolarija/offer_detail.html` — ima li `position:fixed` elem koji izlazi izvan viewporta
- Fix: `overflow-x: hidden` na `.main-content` ili `.content-wrapper`

---

## VOICE V2 — GRADILIŠNO MJERENJE

### Zdenkova ocjena:
> "Dobro je za kod kuće kad se prepisuje bilježnica, a za gradilište nije jer u obadvjema rukama treba biti metar."

### Zahtjev:
**Mikrofon je UVIJEK uključen** — ne treba pritisnuti gumb.
Korisnik govori, AI sluša i automatski parsira.

### Implementacija (redom, ne preskači):

#### FAZA 1 — Continuous voice (HITNO, bez AI)
Fajl: `stolarija/templates/stolarija/measure.html`

```javascript
// UMJESTO: korisnik pritisne gumb → govori → otpusti
// NOVO: stranica se otvori → mikrofon se automatski uključi → stalno sluša

recognition.continuous = true;       // NE restartaj ručno
recognition.interimResults = true;   // prikaži dok govori

// Auto-start kad se stranica učita:
document.addEventListener('DOMContentLoaded', () => {
  // Traži dozvolu i odmah startaj
  startContinuousListening();
});

// Separator: 2 sekunde tišine = kraj jedne mjere → pošalji parser
// Svaki onresult interim → resetiraj timer 2s
// Svaki isFinal → sendToParser()
```

Vizualni indikator: pulsing mic ikona u gornjem desnom kutu (uvijek vidljiva)
Status: "🎙 Slušam..." / "⏸ Pauza" / "✅ Mjera snimljena"

#### FAZA 2 — Slika šalabaktera (OCR import)
Fajl: novi view `stolarija/views.py` + template fragment

```
Gumb: "📷 Slikaj listu mjera"
→ otvori kamera ili file picker
→ POST /hr/stolarija/sesija/{id}/ocr-import/
→ Anthropic Vision API: "Izvuci sve mjere iz slike, format: pozicija, šxv, tip"
→ Prikaži preview za potvrdu → spremi sve mjere odjednom
```

Model za OCR: claude-opus-4-6 (vision)
Prompt template u: `stolarija/ai_prompts.py`

#### FAZA 3 — Slika otvora → AI mjere
Fajl: `stolarija/views.py` + `stolarija/templates/stolarija/photo_measure.html` (postoji!)

```
Gumb: "📷 Slikaj otvor"
→ korisnik slika prozorski otvor
→ POST /hr/stolarija/sesija/{id}/photo-measure/
→ Vision API: "Procijeni dimenzije otvora na slici. Referentna mjera: standardna cijena 8.5cm (ako vidljiva)"
→ Prikaži procijenjene mjere + UPOZORENJE: "AI procjena — izmjeri metrom za potvrdu"
→ Korisnik potvrdi ili ispravi
```

#### FAZA 4 — GPS lokacija (jednostavno)
Uz svako mjerenje spremi GPS koordinate:

```javascript
// U measure.html, uz svako saveanje mjere:
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(pos => {
    document.getElementById('hidGpsLat').value = pos.coords.latitude;
    document.getElementById('hidGpsLng').value = pos.coords.longitude;
    document.getElementById('hidGpsAcc').value = pos.coords.accuracy;
  }, null, {timeout: 5000, enableHighAccuracy: true});
}
```

Model: dodaj polja `gps_lat`, `gps_lng`, `gps_accuracy` na `WindowMeasurement`:
```python
gps_lat = models.FloatField(null=True, blank=True)
gps_lng = models.FloatField(null=True, blank=True)
gps_accuracy = models.FloatField(null=True, blank=True, help_text="Točnost u metrima")
```

#### FAZA 5 — AR mjerenje (dugoročno, NE sada)
```
Mobilom iscrtava po uslikanoj slici + mjerenje povlačenjem
Tehnologija: WebXR API + ARCore/ARKit bridge
Status: BUDUĆE — kad je Faze 1-4 stabilno
```

---

## PRIMJER GLASOVNOG UNOSA (za AI parser)

Korisnik govori:
> "Pozicija jedan — svjetli otvor je 1654 × 1205 — dvokrilni simetrični prozor bez prečke, sa roletom i komarnikom, klupčica od granita 3 centimetra"

AI parsira u:
```json
{
  "position": 1,
  "width_mm": 1654,
  "height_mm": 1205,
  "element_type": "window",
  "wing_config": "double_symmetric",
  "has_transom": false,
  "has_roller_shutter": true,
  "has_mosquito_net": true,
  "windowsill_material": "granite",
  "windowsill_thickness_cm": 3,
  "raw": "Pozicija jedan — svjetli otvor je 1654 × 1205..."
}
```

Separator između mjera: "a između" / "sljedeće" / "pozicija dva" / 2s tišina

---

## LINKABILNOST — GLOBALNO PRAVILO

Svaka mjera mora biti linkabilna:
- U session_detail: `<a href="#m-{{ m.id }}">` + `<div id="m-{{ m.id }}">`
- U offer_detail: `<a href="{% url 'stolarija:session_detail' offer.session.id %}#m-{{ m.id }}">`
- Na print/PDF: URL ponude + QR kod

---

## REDOSLIJED IZVOĐENJA

1. BUG-1: Ponuda se ne otvara → fix + test
2. BUG-2: Stranica desno → fix + test  
3. FAZA 1: Continuous voice → measure.html refactor + test
4. FAZA 4: GPS → migration + JS (brzo, 30 min)
5. FAZA 2: OCR šalabakter → view + Vision API
6. FAZA 3: Slika otvora → Vision procjena
7. FAZA 5: AR → buduće

---

## TEHNIČKI DETALJI

- Voice parser: `stolarija/views.py:voice_parse` (postoji) — proširi za GPS + kontinuiranu upotrebu
- AI prompts: `stolarija/ai_prompts.py` — dodaj `PHOTO_OCR_PROMPT` i `PHOTO_MEASURE_PROMPT`
- Model: `stolarija/models.py:WindowMeasurement` — dodaj GPS polja (nova migracija)
- Templates: `stolarija/templates/stolarija/measure.html` — glavni kandidat za refactor

## ZAVRŠETAK

```
manage.py check → 0 grešaka
git commit --no-verify -m "feat(stolarija): Voice V2 continuous + GPS + OCR import"
Ažuriraj FENIX_STATUS.md GORIVO tablicu
```
