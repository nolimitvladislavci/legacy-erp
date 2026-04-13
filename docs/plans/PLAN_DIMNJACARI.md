# PLAN: Dimnjačari — Komunalni vertikalni modul
**Datum:** 02.04.2026. | **Status:** ZAMRZNUT — ideja za post-launch
**Kontekst:** Ivan bivši upravitelj zgrada, poznaje materiju

---

## Zašto dimnjačari — savršen fit

- Municipalna koncesija (JLS) → poznata materija ✅
- Obavezni periodični pregledi (zakon) → recurring taskovi ✅
- Radni nalog na terenu → BORG dispatch + GPS ✅
- Fiskalizacija na licu mjesta → POS mobilni ✅
- Potvrda o ispravnosti dimnjaka → WeasyPrint PDF ✅
- Evidencija servisa po adresi/zgradi → baza ✅
- Godišnji plan obilazaka → Celery beat ✅

## Zakon
Zakon o obavljanju dimnjačarskih poslova (NN 103/15)
- Obvezna kontrola 1-2x godišnje po dimnjaku
- Potvrda o ispravnosti = zakonska isprava
- Evidencija mora biti dostupna inspekciji

## Što treba izgraditi (80% postoji)
```
✅ BORG dispatch (terenska ekipa)
✅ GPS tracking
✅ POS fiskalizacija mobilna
✅ WeasyPrint potvrde
✅ Komunalni modul (baza)
❌ Dimnjak registar (adresa → katastarska čestica → dimnjak ID)
❌ Periodični plan obilazaka (godišnji raspored)
❌ Predložak "Potvrda o ispravnosti dimnjaka"
❌ Koncesijski ugovor s JLS template
```

## Poslovni model
- 29 EUR/mj — mobilni POS + radni nalozi + potvrde
- JLS modul (koncesija) → posebno
- HR: ~800 registriranih dimnjačarskih obrta (HGK)

---
*Preklapa se s: komunalni modul, BORG dispatch, sezonski radnici*
*Ivan pozadina: upravitelj zgrada — dobra referenca za prodaju*
