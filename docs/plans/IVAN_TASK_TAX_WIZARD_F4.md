# IVAN_TASK_TAX_WIZARD_F4 — Tržište, Distribucija, Launch
## Agent: Ivan | Prioritet: P0 (paralelno s F1-F3) | Horizont: do veljače 2027.

**Ni kod ni tehnika. Ovo je tvoj teren — ljudski kapital i tržišna pozicija.**  
**CC/Gemini/Sonnet grade proizvod. Ti gradiš distribucijsku mrežu bez koje je taj proizvod mrtav.**

---

## TVOJA MISIJA

Taxfix ima 5 milijuna korisnika jer je potrošio **desetke milijuna € na marketing**.  
Mi to nećemo. Naš put je drugačiji: **3.500 Marija diljem Hrvatske šalje linkove svojim klijentima.**

Jedna Marija = 50 klijenata = 50 × 29€ = 1.450€/sezona.  
100 Marija = 145.000€/sezona bez jedne TV reklame.  
3.500 Marija = 5.075.000€ adresabilno tržište (po sezoni, jednom godišnje).

---

## AKCIJA 1: Marija Brtan — Prva Marija (do kraja travnja)

### Što trebaš napraviti

Marija Brtan je naša proof-of-concept partnerica. Ona treba biti **prva koja koristi wizard sa stvarnim klijentima** — prije javnog launcha.

**Konkretan razgovor:**
1. Pokaži joj `SONNET_TASK_TAX_WIZARD_F3.md` — Partner Dashboard section
2. Objasni: "Šalješ link klijentima, oni ispune, ti dobiš gotov XML i 30% provizije automatski"
3. Pitaj: "Koja 3 tvoja klijenta bih mogli biti beta testeri u travnju?"

**Što treba od Marije:**
- Pristanak na beta testiranje s 3-5 klijenata
- Feedback: što nedostaje, što je zbunjujuće
- Preporuke računovođa koje poznaje (za distribucijsku mrežu)

**Setup za Mariju (tehnički — reci CC Code-u):**
```python
PartnerTaxAccount.objects.create(
    company=Company.objects.get(name='Konjik d.o.o.'),
    brand_name='Konjik Porezni Asistent',
    brand_color='#1e3a5f',
    commission_rate=Decimal('0.30'),
    is_active=True,
)
```

---

## AKCIJA 2: HOK (Hrvatska obrtnička komora) — Strateška distribucija

### Zašto HOK

HOK ima **direktan kanal do 60.000+ obrtnika**. Oni već šalju newsletter s uputama za DOH.  
Ako HOK preporuči naš wizard kao "brzi alat za DOH pripremu", mi smo završili s marketingom.

### Kontakt strategija

**Ne idi kao ViB startup. Idi kao rješenje njihovog problema.**

HOK's problem: svake veljače dobivaju tisuće poziva "Kako ispuniti DOH?". To im troši resurse.  
Naše rješenje: "Mi preuzimamo te pozive. Vaši obrtnici odu na link, za 15 min imaju sve podatke."

**Pitch (max 3 rečenice):**
> "HOK svake godine šalje uputu za DOH. Ove godine uz uputu možete poslati i link koji automatski izračuna svačiji obračun iz podataka koje obrtnik već ima. Mi preuzimamo tehničku podršku, vi dobivate branded alat."

**Kontakt:** hok@hok.hr ili direktno Sekcija računovođa HOK-a (oni su preporučili i prihvatili prijedlog izmjene rokova plaćanja!).

**Što nudimo HOK-u:**
- White-label: "HOK Porezni Kalkulator 2025" (njihov branding)
- Besplatno za obrtnike koji su članovi HOK-a (mi zaradimo na premium features)
- HOK dobiva statistike: koliko obrtnika je koristilo, prosječna ušteda

---

## AKCIJA 3: Konjik klijenti — Beta testiranje (travanj)

Konjik ima klijente koji su aktivni ERP korisnici — za njih je wizard najmoćniji jer se pre-popunjava iz faktura.

**Plan:**
1. Identificiraj 5-10 Konjik klijenata koji imaju DOH obvezu (Marija zna)
2. Marija im šalje beta link u travnju
3. Mi pratimo: koliko klikova, gdje odustaju, što ne razumiju
4. Feedback → CC Code/Gemini iterira

**Metrika uspjeha beta testa:**
- Completion rate > 60% (Taxfix ima ~65% u DE)
- Prosječno vrijeme: < 20 minuta
- NPS > 7/10

---

## AKCIJA 4: WhatsApp kampanja — Sezonska (veljaška 2027)

### Plan kampanje (počinje 20. siječnja 2027.)

```
Tjedan -2 (20. siječnja):
  "Rok za DOH prijavu je za 2 tjedna. Provjeri imaš li pravo na povrat — besplatno:"
  → link na kalkulator (bez registracije)

Tjedan -1 (27. siječnja):
  "Pronašao si olakšice? Za predaju DOH-a trebaš još samo 10 minuta:"
  → link na paid submit

Dan -1 (1. veljače):
  "SUTRA je rok. Još nisi predao? Pošalji nam podatke, mi odrađujemo:"
  → emergency paket (49€)

Dan 0 (2. veljače — ROK):
  "Rok je prošao. Ali za ZPP-DOH imaš još malo vremena..."
  → ZPP-DOH upsell (9,99€)
```

**Ciljne liste:**
- Svi POS korisnici (paušalisti — PO-SD)
- Svi invoicing korisnici (obrtnici s knjigama — DOH)
- Partnerske liste računovođa

---

## AKCIJA 5: SEO priprema (od travnja)

Ove ključne riječi u 2026. nemaju ozbiljne konkurencije:

| Ključna riječ | Volumen/mjes | Konkurencija |
|---|---|---|
| "porezna prijava obrtnik 2026" | ~1.200 | Niska |
| "DOH obrazac popunjavanje" | ~800 | Niska |
| "povrat poreza mladi Hrvatska" | ~600 | Niska |
| "ZPP-DOH kako popuniti" | ~400 | Niska |
| "porezne olakšice obrtnik" | ~500 | Niska |

**Akcija:** Napiši 5 SEO članaka (400-600 riječi, konkretan sadržaj) i postavi na limit-connect.com/blog ili /vodici/. Svaki članak završava s CTA-om na kalkulator.

---

## AKCIJA 6: Banke i sindikati (Q3 2026 — strateški)

### Zašto banke

Privredna banka, Erste, OTP — sve imaju ~500.000 klijentima koji imaju DOH obvezu.  
Ponuda: "Vaši klijenti dobivaju besplatni porezni kalkulator u vašem app-u."  
Model: banka plaća flat fee, mi distribuiramo.

### Zašto sindikati

SSSH (Savez samostalnih sindikata) ima 200.000 članova — radnici koji mogu koristiti ZPP-DOH.  
Jednokratna ponuda: "Besplatni porezni vodič za vaše članove."

---

## PRICELIST za distribucijsku mrežu

| Tip partnera | Model | Cijena |
|---|---|---|
| Računovođa (Marija model) | 30% provizija per submit | 0€ ulaz, earn per click |
| HOK white-label | Godišnja licenca | 2.400€/god |
| Banka white-label | Godišnja licenca + per-user | 12.000€/god + 2€/korisnik |
| Sindikat/komora | Flat fee godišnja | 3.600€/god |

---

## TVOJ TRACKER — što moraš imati DONE do 30. travnja

```
[ ] Razgovor s Marijom — beta pristanak i 3 test klijenta
[ ] PartnerTaxAccount kreiran za Konjik d.o.o.
[ ] Email HOK-u (Sekcija računovođa) — pitch poslan
[ ] 5 beta klijenata identificirano
[ ] SEO članak #1 napisan i postavljen
[ ] WhatsApp kampanja plan finaliziran (tekst + lista)
[ ] Pitch deck za banke — 1 stranica, PDF (CC Code može napraviti)
```

---

## JEDNA STVAR KOJU MORAŠ ZAPAMTITI

Taxfix je unicorn ne zato što je softver bolji od excela.  
Taxfix je unicorn zato što je **napravio da bol nestane u 30 minuta**.

Mi imamo nešto što Taxfix nema: **podatke već unutra**.  
Marija's klijent ne otvara prazan form — otvara form gdje piše "Iz tvojih faktura: 28.430€."  
Taj trenutak, kad korisnik vidi da sustav **zna** — to je naš viralni moment.  
Marija će to pripovijedati svakom računovođi kojeg poznaje.  
Usta do usta, bez marketinškog budžeta.

**Jedan zadovoljni korisnik koji je vratio 847€ je bolji od 1.000€ Google Adsa.**
