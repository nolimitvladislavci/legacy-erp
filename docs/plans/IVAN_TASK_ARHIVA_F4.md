# IVAN_TASK_ARHIVA_F4 — Marija Onboarding + Feedback
## Agent: Ivan | Paralelno s F1-F3

---

## TVOJA MISIJA DANAS

Dok trojica grade, ti pripremaš Mariju na testiranje.  
Cilj: Marija testira scan batch do kraja dana s pravim računima.

---

## AKCIJA 1 — Pripremi Mariji scenarij testiranja

Marija ne testira "da li radi". Testira konkretne scenarije:

**Scenarij A — Batch paušalista (jednostavan):**
1. Slika 5-10 računa s poda (Konzum, Lidl, benzinska...)
2. Klikne "Analiziraj"
3. AI prepozna dobavljače i iznose
4. Klikne "Spremi u arhivu"
5. Vidi dokumente u arhivi odmah

**Scenarij B — Višestranični račun (pravi test):**
1. Fotokopira jedan dvostranični ili trostranični račun
2. Slika obje/tri stranice uzastopno
3. AI treba prepoznati da su to iste stranice i spojiti ih
4. Provjeri: u arhivi se pojavljuje kao JEDAN dokument, ne dva

**Scenarij C — Mješoviti batch (30 slika):**
1. Mix HR i DE računa (Marija ima i DE klijente)
2. Slika brzo, bez sortiranja
3. AI treba sve prepoznati
4. Provjeri: sve prepoznato, ništa nije propalo

---

## AKCIJA 2 — Objasni Mariji AI ograničenja (честno)

**Što AI radi dobro:**
- Čisti, jasni računi: 95%+ točnost
- HR i DE jezik podjednako
- Automatska detekcija OIB/USt-IdNr
- Iznosi uvijek točni (matematika je matematika)

**Što AI ne radi savršeno:**
- Loša fotografija (mutno, zasjenjeno) → manja točnost
- Ručno pisani računi → OCR može pogriješiti
- Stari računi s izbljedjelim tekstom
- Ako dobavljač nema OIB na računu → upozorenje ali sprema se

**Ključna poruka za Mariju:**
> "AI priprema, ti odobrava. Svaki dokument vidiš prije nego ga stavi u arhivu.  
> Ništa se ne sprema bez tvog klika 'Spremi u arhivu'."

---

## AKCIJA 3 — Skupi feedback strukturirano

Za svaki scenarij, Marija bilježi:

| Scenarij | Radi? | Što nedostaje? | Što ne radi? |
|----------|-------|----------------|--------------|
| A — 5 računa | | | |
| B — višestranični | | | |
| C — 30 slika | | | |

**3 najvažnija pitanja:**
1. "Jesi li bila sigurna što trebas kliknuti u svakom koraku?"
2. "Je li AI prepoznao tvoje dobavljače točno?"
3. "Što bi promijenila da koristiš ovo svaki dan?"

---

## AKCIJA 4 — Registar iznajmljivača (planiraj za tjedan 2)

Marija je rekla da ima klijente iznajmljivače. Ovo je novi feature koji dolazi NAKON arhive.

**Što trebamo od Marije:**
- Koliko klijenata iznajmljivača ima?
- Koje obrasce puniti za njih sada? (TZ-2, EP obrazac, PO-SD)
- Koji je najveći problem s iznajmljivačima sada?

Ovo je ulaz za `CC_TASK_REGISTAR_IZNAJMLJIVACA_F1.md` koji pišemo sljedeći tjedan.

**Kratki summary što ćemo graditi:**
- Registar objekata (naziv, kategorizacija, broj kreveta, JLS)
- Popis gostiju (digitalna knjiga, eVisitor XML export)
- Kalkulator paušalnog poreza (po krevetu × JLS stopa)
- TZ-2 obrazac generacija (godišnje, do 15. siječnja)
- Evidencija prometa / EP obrazac (automatski iz računa)

---

## DONE kriterij

```
[ ] Marija je testirala Scenarij A (5 računa → arhiva)
[ ] Marija je testirala Scenarij B (višestranični)
[ ] Feedback tablica popunjena
[ ] Podaci o iznajmljivačima prikupljeni za F1
```
