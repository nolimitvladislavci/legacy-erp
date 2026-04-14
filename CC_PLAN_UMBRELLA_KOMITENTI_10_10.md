# PLAN: Umbrella Komitenti — 10/10 Rješenje + 2 Inovacije iz Budućnosti

**Status**: U TIJEKU
**Datum**: 2026-04-14
**Prioritet**: KRITIČAN — prelomni trenutak za EU #1

---

## DIJAGNOZA — Što je pronađeno

### Stanje baze (Konjik d.o.o. — 52e2e048):
- **is_umbrella**: true, **umbrella_max_children**: 72
- **Stvarnih djece**: 81 (prekoračen limit!)
- **5 desk workspace-ova**: Ljiljana+Anita (14 klijenata), Maja (13), Nikolina (13), Slađana (15), Sanela+Silvija (13)
- **6 premise workspace-ova**: Recepcija SIM, Blagajna, KS Limit, Optika x3

### Agrovladislavci (5c4cd3be):
- **umbrella_parent**: Konjik ✅
- **umbrella_relation**: client ✅
- **KomitentProfile**: active ✅
- **Workspace**: #1 Ljiljana+Anita ✅
- **CompanyPartnership**: postoji, full access ✅
- **Subscription**: `pos-besplatno` (samo POS, partners, inventory, tax_wizard)
- **CompanyModuleConfig**: PRAZNO — nijedan modul nije eksplicitno omogućen

### Pronađeni BUG-ovi:

#### BUG 1: Umbrella Switch Radi Samo Za Direktnu Djecu
```python
# umbrella_switch_company (line 852):
child = Company.objects.get(pk=company_id, umbrella_parent=user_company)
# get_user_company (line 33):
if child.umbrella_parent_id == profile_company.id:
```
Samo 1 razina dubine. Viktor Grgurić (sub-umbrella, distributer) ima `is_umbrella=true` i `umbrella_parent=Konjik`.
Njegova djeca NIKAD ne mogu biti switchana od strane Konjik admina.

#### BUG 2: 9 Djece Bez Workspace-a
Brunoslav Horvat, Dbg2, Debug, Fiskaly Test, KUD DUKAT, Viktor Grgurić, Viskovic Bau, VODOCOMP, Zdenko Šoš
— **Ne pojavljuju se u desk pregledima** knjigovodstva.

#### BUG 3: 9 Djece Bez CompanyPartnership
Ista lista — **nema formalne veze** za pristup/billing.

#### BUG 4: Subscription Mismatch za Klijente Knjigovodstva
Agrovladislavci ima `pos-besplatno` → ne uključuje: `invoicing`, `documents`, `konto`, `eracun`, `finance`.
Knjigovođa kad switcha na Agrovladislavci vidi upgrade bannere svugdje.

#### BUG 5: umbrella_max_children = 72, Stvarno Djece = 81
Limit je prekoračen ali **nema enforceanja** — tiha greška.

#### BUG 6: Nema "Bookkeeper Plan" za Umbrella Djecu
Umbrella djeca trebaju NASLIJEDITI module od roditelja za kontekst knjigovodstva.
Trenutno: svako dijete ima svoj plan, često neadekvatan.

---

## RJEŠENJE — 3 Faze

### FAZA 1: Hitni Popravak (Agrovladislavci + Integritet)
1. **Subscription Fix**: Umbrella djeca nasljeđuju module roditelja kad su u umbrella kontekstu
2. **Workspace Assignment**: Dodaj 9 neraspoređenih klijenata u workspace ili označi ih
3. **Partnership Sync**: Kreiraj CompanyPartnership za svih 9 koji nemaju
4. **Max Children**: Ažuriraj umbrella_max_children na stvarni kapacitet (100)

### FAZA 2: Dubinski Popravak Umbrella Mehanizma
1. **Multi-Level Switch**: Podrška za grandchild switching (3 razine dubine)
2. **Module Inheritance**: Kad bookkeeper gleda klijenta, koristi module umbrella roditelja
3. **Workspace Integration**: Iz workspace view-a direktan klik → umbrella switch na klijenta
4. **Breadcrumb Navigation**: Konjik → Ljiljana+Anita → Agrovladislavci (vizualni kontekst)
5. **Quick Switch Dropdown**: U headeru, brzi switch između klijenata bez povratka na dashboard

### FAZA 3: Inovacije Budućnosti (+2)

#### INOVACIJA 1: "Smart Desk" — AI Raspodjela Klijenata po Workspace-ima
- AI analizira obujam posla (fakture, knjiženja, rokove) za svakog klijenta
- Automatski predlaže preraspodjelu klijenata među desks-ovima za optimalno opterećenje
- "Ljiljana+Anita imaju 30% više posla od Nikoline → predlaži premještaj 3 klijenta"
- Dashboard: heatmap opterećenja po desk-u, trendovi, upozorenja na nebalans

#### INOVACIJA 2: "Client Pulse" — Real-Time Zdravlje Klijenta
- Za svaku umbrella djecu: zeleno/žuto/crveno stanje
- Automatski izračun: nepredane PDV prijave, neobrađeni izvodi, kasni dokumenti
- WhatsApp notifikacija klijentu: "Agrovladislavci, fali nam faktura za 03/2026"
- Timeline: kad je zadnji put knjigovođa radio na ovom klijentu, koliko je vremena uloženo
- Prediktivni model: "Ovaj klijent će kasniti s PDV prijavom baziran na povijesnom obrascu"

---

## IMPLEMENTACIJA — Detaljni Koraci

### Korak 1: Module Inheritance Engine
Lokacija: `core/company_utils.py`
- Nova funkcija `get_effective_modules(company, request)`:
  - Ako je `umbrella_as_company` aktivan, vrati UNIJU modula djeteta i roditelja
  - Ovo osigurava da bookkeeper ima pristup svemu što treba

### Korak 2: SubscriptionMiddleware Patch
Lokacija: `registration/middleware.py`
- `_check_subscription` treba koristiti `get_effective_modules` umjesto samo plana djeteta

### Korak 3: Multi-Level Switch
Lokacija: `core/views.py` (umbrella_switch_company) + `core/company_utils.py` (get_user_company)
- Provjera svih predaka (child.umbrella_parent → parent.umbrella_parent → ...) umjesto samo 1 razine

### Korak 4: Data Integrity Fix
SQL: popuni workspace_clients, partnership, ažuriraj max_children

### Korak 5: Quick Switch UI
Lokacija: `templates/base.html` — dropdown u headeru sa svim klijentima trenutnog workspace-a

### Korak 6: Smart Desk (Inovacija 1)
Model: `companies/models.py` — WorkloadSnapshot
View: `core/views.py` — umbrella_smart_desk
Celery task: dnevni izračun opterećenja

### Korak 7: Client Pulse (Inovacija 2)
Model: `companies/models.py` — ClientHealthScore
View: `core/views.py` — client_pulse_dashboard
Celery task: hourly health check
WhatsApp integration: via WAHA

---

## REDOSLIJED IMPLEMENTACIJE
1. ✅ Plan napisan
2. ⬜ Korak 4: Data Integrity (SQL) — ODMAH
3. ⬜ Korak 1+2: Module Inheritance — 30 min
4. ⬜ Korak 3: Multi-Level Switch — 20 min
5. ⬜ Korak 5: Quick Switch UI — 30 min
6. ⬜ Korak 6: Smart Desk model+task — 45 min
7. ⬜ Korak 7: Client Pulse model+task+whatsapp — 60 min
8. ⬜ Test: HR/DE/EN + mobile — 15 min
