# BOXGRAM_STATUS.md
# Boxgram — Jedini izvor istine
# Zadnje ažuriranje: 05.04.2026.

## FILOZOFIJA
"Preslika vanjskog života u digitalni portal — od rođenja do zauvijek."
Instagram briše. Boxgram ne.

## PLATFORMA
- URL: https://memio.pet (Boxgram social layer)
- Django app: boxgram/ (unutar fina-connect projekta)
- Server: 37.27.248.86

## PILOT KORISNICI (čekaju)
- Ljubeta (Novaki) — uzgajivač pasa — čeka link
- Pero Lapis — pčelar (OPG) — čeka link
- 3 korisnika s memio.pet waitliste

## FAZE

### FAZA 0 — MVP (ovaj tjedan)
Status: 🔄 U tijeku

[ ] CC_TASK_BOXGRAM_CORE.md — modeli + API
[ ] GEMINI_TASK_BOXGRAM_REVIEW.md — review + UX spec
[ ] boxgram/ Django app kreirana
[ ] Migracije
[ ] Javni profil ljubimca: memio.pet/ljubimac/{slug}/
[ ] Timeline (3 event tipa: rodenje, vet, nagrada)
[ ] Registracija ljubimca (3 koraka)
[ ] QR kod generiranje

### FAZA 1 — Social (sljedeći tjedan)
Status: ⏳ Čeka Fazu 0

[ ] Social import (URL lijepljenje + oEmbed)
[ ] Takmičenje MVP (glasovanje po IP)
[ ] Foto galerija
[ ] Share → WhatsApp/FB
[ ] Prati ljubimca

### FAZA 2 — Dubina (travanj/svibanj)
Status: ⏳ Čeka Fazu 1

[ ] FB/IG OAuth import (+ Meta App Review)
[ ] TimeCapsule / Memorial mode
[ ] Rodovnica + SHA256 pečat
[ ] Kennel profil (uzgajivači)
[ ] Pčelar modul (košnice, matice, rojevi)
[ ] HAPIH export (CSV za pčelare)

### FAZA 3 — EU
Status: ⏳ Long term

[ ] 5 EU jezika (EN, DE, SLO, IT, HR)
[ ] Pan-europska takmičenja
[ ] Veterinarski partneri
[ ] EU fondovi prijava (NO LIMIT udruga)
[ ] memio.pet/en/ multilingval routing

## KATEGORIJE LJUBIMACA
pas, macka, konj, zec, ptica, riba, pcela, govedo, svinja, ovca, koza, ostalo

## SPECIJALNE KATEGORIJE
- Kennel / Uzgajivač (firma profil)
- OPG Pčelar (košnice kao ljubimci)
- Verificirani vet partneri

## ARHITEKTURA
Models: PetProfile, LifeEvent, EventMedia, SocialImport,
        Competition, CompetitionEntry, CompetitionVote,
        PetFollower, EventHeart

Celery taskovi (queue=default):
  - close_competition
  - fetch_social_import
  - generate_pet_qr

## POZNATI PROBLEMI / TODO
- CompetitionVote unique_together bug — Gemini da ispravi
- qrcode[pil] library — dodati u requirements.txt
- oEmbed rate limits — dodati caching
- Meta App Review za user_posts — paralelno pokrenuti

## EKIPA
- Sonnet: koordinator, arhitekt, taskovi
- CC Code: backend implementacija
- Gemini: arhitektura review + adversarial
- Ivan: pilot korisnici, WhatsApp komunikacija
