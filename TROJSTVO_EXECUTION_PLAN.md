# TROJSTVO EXECUTION LAYER
> Autor: Sonnet | Datum: 2026-04-17 | Status: PRIORITET 1
> Žuti karton prihvaćen. Ovo je ispravljeni plan.

---

## DIJAGNOZA

**Trojstvo danas:**
- 1.281 analiza u bazi
- 13 done (1%)
- 1.261 "reviewed" = dijagnosticirano ali neizvršeno
- Trojstvo je dijagnostičar bez kirurga

**Uzrok:**
Nema automatskog puta od KONSENZUS → CC_TASK → Implementacija.
Ivan mora ručno preuzeti svaku poruku s WhatsAppa i pretvoriti u zadatak.
To nije 13/10 — to je bottleneck.

---

## RJEŠENJE: EXECUTION LAYER

### Faza 1 — Auto CC_TASK Generator (odmah)

Kad Trojstvo postigne ≥85% konsenzus:
1. Automatski kreira `CC_TASK_AUTO_{id}_{slug}.md` u `/var/www/fina-connect/`
2. Task file sadrži: dijagnozu, rješenje, affected files, testove
3. WhatsApp Ivanu: "✅ Task kreiran: {naslov}. CC može početi."
4. Ivan samo kaže "pokreni" — ne mora ništa pisati

### Faza 2 — Trojstvo Dashboard (ova sesija)

Stranica `/admin/trojstvo/` prikazuje:
- Top 10 analize po prioritetu (agreed, visoki prioritet)
- Jedan klik → "Generiraj CC Task"
- Status: Pending / CC In Progress / Done / Rejected
- Filteri: firma, kategorija, prioritet, datum

### Faza 3 — Automatic Triage (sljedeća sesija)

Klasifikacija bez WhatsAppa:
- "odmah" + ≥90% + sigurnosni problem → CC_TASK automatski, bez pitanja
- "ovaj-tjedan" + ≥85% → CC_TASK kreiran, WhatsApp obavijest
- "sljedeci-sprint" + ≥70% → batching, jednom tjedno summary

---

## AI COST MODEL — ISPRAVLJENI

| Component | Model | Trošak | Napomena |
|-----------|-------|--------|----------|
| Trojstvo Glasač 1 | Haiku (API) | ~$5/mj | Platformski pozivi |
| Trojstvo Glasač 2 | Gemini Flash | ~$0 | Vlastiti key |
| Trojstvo Glasač 3 | DeepSeek/Devstral (Bedrock) | AWS ~$2/mj | GDPR OK |
| Trojstvo Konsenzus | Haiku (downgrade) | ~$2/mj | Sonnet → Haiku |
| Ivan dev sesije | claude.ai Max plan | $0 extra | MCP pokriva sve |
| CC Code taskovi | Max plan | $0 extra | Prijavljen, ne API |
| **UKUPNO API** | | **~$9/mj** | Cilj |

---

## ŠTO RADIMO SA 1.261 REVIEWED ANALIZOM

Ne implementiramo sve retroaktivno — to je kaos.

Plan:
1. Filter: `status='reviewed', priority>=4, trojstvo_status='agreed'` → top 20
2. Grupiraj po kategoriji: db_indexi, N+1 queriji, sigurnost, validacija
3. Batch CC_TASK po kategoriji (ne 20 odvojenih)
4. Implementirati redom: sigurnost → performance → kvaliteta koda

Konkretno što Trojstvo preporučuje (danas, odmah):
- Payment model: 4 indeksa (status, method, created_at, composite)
- ERacun: indeks na status polju
- RecallNotification: select_related u admin
- 9 radnika bez OIB-a: validacija na model razini
- payment_success/payment_cancel: @login_required

Ovo je ~2 sata CC Code rada. Ne tjednima — satima.

---

## FENIX ZAKON — ŠTO SMO PREKRŠILI

Pravilo 0: "Svaka sesija počinje s git log i FENIX_STATUS.md"
→ Sonnet nije imao pregled API troškova u kontekstu. Nije surfaced proaktivno.

Pravilo 1: "13/10 je minimum"
→ Trojstvo na 1% efikasnosti nije 13/10. To je 1/10.

Pravilo 0 (aktivna primjena): "Laskanje ubija projekte"
→ U prethodnom odgovoru pitao sam Ivana umjesto da dam analizu.
→ To se ne ponavlja.

---

## SLJEDEĆI KORACI (redoslijed, ne datumi)

1. Fix Trojstvo konsenzus model: Sonnet → Haiku (napravljeno ✅)
2. Implementirati top 5 Trojstvo preporuka (CC_TASK)
3. Izgraditi Trojstvo Execution Layer (auto CC_TASK generator)
4. Trojstvo Dashboard u admin sučelju
5. Tjedni Trojstvo report umjesto dnevnih WhatsApp ponavljanja

