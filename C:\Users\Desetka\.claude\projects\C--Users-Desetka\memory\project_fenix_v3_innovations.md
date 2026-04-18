---
name: Fenix V3 — Innovation Pipeline
description: Ideas from Gemini, DeepSeek, and CC for Fenix v3 — three future layers beyond foundation
type: project
---

# Fenix V3 — Innovation Pipeline (2026-04-17)

## GEMINI PRIJEDLOZI (ETON 13/10)
1. **Identity Core** — Full Identity Orchestration: IP subnet fingerprint, Trust Score per session, Rate limiting per tenant. Ne samo "jesi li ulogiran" nego "koliko ti vjerujem."
2. **Voice/AI Shell** — Globalni async listener u base templateu. Uvijek sluša, nikad ne blokira. Spremno za glasovne komande bez ijednog klika.
3. **PermissionCheck u BaseView** — Ugrađeni permission layer u svakoj klasi, ne decorator na URL-u. View se sam štiti.
4. **Tenant Logic na razini modela** — Automatsko filtriranje podataka po firmi. Nemoguće zaboraviti `.filter(company=...)`.

## DEEPSEEK UPOZORENJA (3 ZAMKE)
1. **Multi-Tenant SQL injection kroz JSONField** — Ne koristiti raw SQL na JSONField. Validator za svaki JSON ulaz.
2. **UUID sudar pri migraciji između firmi** — UUID v7 (timestamp-uredan) + prefiks po firmi umjesto v4.
3. **Async taskovi koji gutaju memory** — Celery s rate limitom po firmi. Redis maxmemory politika. Bez toga 80 firmi ubije worker.

## DEEPSEEK NOVINE (3 INOVACIJE)
1. **Trust Score** — Svaki zahtjev ima reputaciju. Ne samo IP, nego ponašanje (koliko grešaka, koliko brzo klikće, je li bot).
2. **Voice/AI listener** — Korisnik priča, sustav sluša. Bez JS frameworka, čisti Alpine + Web Speech API.
3. **Audit Trail na razini modela** — Svaka promjena svakog polja se logira automatski. Ne može se zaobići ni iz shella.

## CC (CLAUDE CODE) — 3 INOVACIJE IZMEĐU SADAŠNJOSTI I BUDUĆNOSTI

### 1. KORISNIČKO ISKUSTVO: Kontekstualni Radni Prostor (Adaptive Workspace)
**Što:** UI se automatski prilagođava korisniku — ne samo tema i jezik, nego RASPORED elemenata. Knjigovođa vidi račune i PDV prvo. Stolar vidi narudžbe i materijal. Pekar vidi POS i inventuru. Invalidan korisnik vidi uvećane gumbe i glasovne prečice.
**Zašto je između sadašnjosti i budućnosti:** Danas svi ERP-ovi daju isti dashboard svima. Sutra će AI u potpunosti generirati UI. Između: sistem koji uči iz prvih 10 klikova i preslože sidebar, kartice i prečice za tog korisnika.
**Implementacija:** `WorkspacePreset` model (role → layout mapping) + `UserBehaviorLog` (klik heatmap, 7-dnevni window) + HTMX partial swap za dinamički dashboard.

### 2. AI INTEGRACIJA: Tihi Dvojnik (Silent Twin)
**Što:** Svaki korisnik ima AI "dvojnika" koji prati rad i uči obrasce. Ne predlaže — anticipira. Kad Marija svaki ponedjeljak kreira fakture za iste klijente, dvojnik ih već ima pripremljene u draft-u kad se ulogira u ponedjeljak ujutro. Kad Antonio svaki dan u 16h zatvara kasu, dvojnik već počne generirati dnevni izvještaj u 15:55.
**Zašto je između:** Danas AI čeka pitanje. Sutra AI radi autonomno. Između: AI koji tiho priprema ali nikad ne izvršava bez potvrde. Pripremi draft → korisnik potvrdi jednim klikom.
**Implementacija:** `BehaviorPattern` model (user + action + timing + frequency) + Celery periodic task koji analizira obrasce + `DraftAction` queue koji korisnik vidi kao "Pripremljeno za vas" karticu na dashboardu.

### 3. SIGURNOST: Geofence + Device Fingerprint Chain (Lanac Povjerenja)
**Što:** Sustav gradi "lanac povjerenja" za svaki uređaj. Prvo korištenje = nepoznat uređaj, traži 2FA. Treće korištenje s iste lokacije = pouzdan, samo PIN. Pristup iz nove države = hard block + WhatsApp obavijest vlasniku firme. Svaka sesija ima fingerprint (browser + OS + screen + timezone + IP subnet) koji se hashira i uspoređuje.
**Zašto je između:** Danas imamo username/password. Sutra passkey/biometrija. Između: sustav koji implicitno gradi profil uređaja i automatski eskalira/deeskalira auth zahtjeve bez da korisnik ikad mora "dodati uređaj" ručno.
**Implementacija:** `DeviceTrust` model (fingerprint_hash, trust_level 0-100, last_seen, location_history) + middleware koji automatski računa trust score + progressive auth (trust < 30 = full 2FA, trust 30-70 = PIN, trust > 70 = auto-login s cookie).

---

**Prioritet implementacije:**
1. Adaptive Workspace — Reservoir 3 (kad dashboard ima prave podatke)
2. Silent Twin — Reservoir 4 (kad imamo 30+ dana korisničkih podataka)
3. Device Trust Chain — Reservoir 2 (odmah nakon auth hardening)
4. Gemini Identity Core — Reservoir 2 (spaja se s Device Trust)
5. DeepSeek Audit na modelu — Reservoir 2 (django-simple-history ili custom signal)
6. UUID v7 migracija — Reservoir 3 (kad počne data migration iz v1)
