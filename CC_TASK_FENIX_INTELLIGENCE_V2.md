# CC Task — Fenix Intelligence v2: Korekcija i zatvaranje kruga

## Kontekst (pročitaj sve prije koda)

```bash
cat /var/www/fina-connect/FENIX_STATUS.md
cat /var/www/fina-connect/CC_TASK_FENIX_INTELLIGENCE.md  # stari task — temelj
cat /var/www/fina-connect/ai_assistant/tools.py           # 21 alat već postoji
cat /var/www/fina-connect/ai_assistant/tool_handlers.py   # handleri za sve alate
cat /var/www/fina-connect/superadmin_ai/services.py       # AIGate — 4 razine pristupa
cat /var/www/fina-connect/ai_assistant/claude_client.py   # SYSTEM_PROMPT, chat_with_claude()
```

## Što je Sonnet otkrio (i što ti kao CC Code trebaš znati)

Gemini je predložio "Function Calling" kao novu stvar. Nije nova — postoji od ranije:
- `tools.py` ima 21 definiran alat (search_articles, get_today_revenue, run_test_suite...)
- `tool_handlers.py` ima handlere za sve
- `AIGate` ima 4 razine: DISABLED / READ_ONLY / ASSISTED / AUTONOMOUS
- `chat_with_claude()` već šalje `tools=TOOLS` u svaki API poziv

**Dakle: infrastruktura postoji. Fale konkretni alati za nove module.**

## Što treba dodati

### Dio A — Novi alati u tools.py (4 alata)

Svaki novi alat prati isti pattern:
1. Definicija u `tools.py` (JSON schema)
2. Handler u `tool_handlers.py` (Python funkcija)
3. Registracija u `handle_tool_call()` dispatch rječnik

#### Alat 1: `get_fund_opportunities`
```python
# tools.py definicija:
{
    "name": "get_fund_opportunities",
    "description": "Dohvati relevantne EU fondove i HR poticaje za firmu. Filtrira po tipu firme (OPG, udruga, d.o.o.), roku prijave i iznosu. Koristi Intelligence modul.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tip": {
                "type": "string",
                "description": "Tip: eu_fond, hr_poticaj, bio_certifikacija, sve (default: sve)",
                "enum": ["eu_fond", "hr_poticaj", "bio_certifikacija", "sve"]
            },
            "rok_dana": {
                "type": "integer",
                "description": "Fondovi koji ističu za N dana (default: 90)"
            },
            "samo_aktivni": {
                "type": "boolean",
                "description": "Samo aktivni natječaji (default: true)"
            }
        }
    }
}

# tool_handlers.py handler:
def _get_fund_opportunities(params, user, company):
    """
    Pazi: intelligence app možda još nije instaliran (CC_TASK_FENIX_INTELLIGENCE).
    Koristi try/except i vrati fallback ako modeli ne postoje.
    """
    try:
        from intelligence.models import FundOpportunity
        from django.utils import timezone
        today = timezone.now().date()

        tip = params.get('tip', 'sve')
        rok_dana = params.get('rok_dana', 90)
        samo_aktivni = params.get('samo_aktivni', True)

        qs = FundOpportunity.objects.all()
        if samo_aktivni:
            qs = qs.filter(status='aktivan')
        if tip != 'sve':
            qs = qs.filter(tip__startswith=tip.replace('eu_fond', 'eu').replace('hr_poticaj', 'hr'))
        if rok_dana:
            qs = qs.filter(rok_prijave__lte=today + timezone.timedelta(days=rok_dana))

        # Filtriraj po tipu firme
        biz_type = getattr(company, 'business_type', '')
        if biz_type == 'opg':
            qs = qs.filter(ciljna_skupina__in=['opg', 'svi'])
        elif biz_type in ('udruga', 'kud', 'sport'):
            qs = qs.filter(ciljna_skupina__in=['udruga', 'svi'])

        rezultati = []
        for f in qs.order_by('rok_prijave')[:10]:
            days = f.days_until_deadline
            rezultati.append({
                'naziv': f.naziv,
                'tip': f.get_tip_display(),
                'tijelo': f.tijelo,
                'iznos_max_eur': float(f.iznos_max_eur) if f.iznos_max_eur else None,
                'rok_prijave': str(f.rok_prijave) if f.rok_prijave else None,
                'preostalo_dana': days,
                'hitno': f.hitno,
                'ai_summary': f.ai_summary[:200] if f.ai_summary else '',
                'checklist': f.ai_checklist[:3] if f.ai_checklist else [],
                'url': f.url,
            })

        return {
            'ukupno': qs.count(),
            'prikazano': len(rezultati),
            'fondovi': rezultati,
            'napomena': f'Firma: {company.name} ({biz_type})',
        }
    except ImportError:
        return {
            'error': 'Intelligence modul još nije instaliran.',
            'info': 'Pokrenite CC_TASK_FENIX_INTELLIGENCE.md za aktivaciju.',
        }
```

#### Alat 2: `get_livestock_status`
```python
# tools.py definicija:
{
    "name": "get_livestock_status",
    "description": "Status farme goveda za OPG. Broj grla, zdravstveni alarmi, mlijeko danas, krave koje tele uskoro, plan sjetve. Samo za OPG firme.",
    "input_schema": {
        "type": "object",
        "properties": {
            "detalji": {
                "type": "string",
                "description": "Što prikazati: pregled, zdravlje, mlijeko, usjevi (default: pregled)",
                "enum": ["pregled", "zdravlje", "mlijeko", "usjevi"]
            }
        }
    }
}

# handler:
def _get_livestock_status(params, user, company):
    try:
        from livestock.models import Livestock, HealthRecord, MilkRecord, CropPlan
        from django.utils import timezone
        today = timezone.now().date()
        detalji = params.get('detalji', 'pregled')

        if getattr(company, 'business_type', '') != 'opg':
            return {'info': 'Livestock modul dostupan samo za OPG firme.'}

        grla = Livestock.objects.filter(company=company)
        if detalji == 'pregled':
            return {
                'ukupno_grla': grla.count(),
                'aktivnih': grla.filter(status='aktivno').count(),
                'gravidnih': grla.filter(status='gravidno').count(),
                'teli_uskoro': grla.filter(
                    expected_calving__lte=today + timezone.timedelta(days=21),
                    expected_calving__gte=today, status='gravidno'
                ).count(),
                'u_karenciji': HealthRecord.objects.filter(
                    animal__company=company,
                    karencija_do__gte=today
                ).count(),
                'bio_grla': grla.filter(is_organic=True).count(),
            }
        elif detalji == 'zdravlje':
            alarmi = HealthRecord.objects.filter(
                animal__company=company,
                karencija_do__gte=today
            ).select_related('animal')[:10]
            return {
                'u_karenciji': [
                    {
                        'grlo': r.animal.ear_tag,
                        'lijek': r.lijek,
                        'karencija_do': str(r.karencija_do),
                        'preostalo_dana': (r.karencija_do - today).days,
                    } for r in alarmi
                ]
            }
        elif detalji == 'mlijeko':
            jucer = today - timezone.timedelta(days=1)
            mr = MilkRecord.objects.filter(animal__company=company, datum=jucer)
            from django.db.models import Sum
            agg = mr.aggregate(ukupno=Sum('ukupno_l'))
            return {
                'datum': str(jucer),
                'ukupno_litara': float(agg['ukupno'] or 0),
                'broj_krava': mr.count(),
                'prosjek_po_kravi': round(float(agg['ukupno'] or 0) / max(mr.count(), 1), 2),
            }
        elif detalji == 'usjevi':
            planovi = CropPlan.objects.filter(company=company).order_by('-godina')[:5]
            return {
                'planovi': [
                    {
                        'kultura': p.get_kultura_display(),
                        'godina': p.godina,
                        'status': p.get_status_display(),
                        'za_prodaju': p.za_prodaju,
                        'visak_t': float(p.procijenjeni_višak_t) if p.procijenjeni_višak_t else None,
                        'auto_listing_spreman': p.auto_listing_ready,
                    } for p in planovi
                ]
            }
    except ImportError:
        return {'error': 'Livestock modul još nije instaliran.'}
```

#### Alat 3: `create_futures_listing` (ASSISTED razina)
```python
# tools.py definicija:
{
    "name": "create_futures_listing",
    "description": "ASSISTED: Objavi višak usjeva ili proizvoda na Burzi kao FuturesListing. Prolazi kroz AIGate ASSISTED razinu — čeka potvrdu vlasnika. Samo za OPG firme.",
    "input_schema": {
        "type": "object",
        "properties": {
            "crop_plan_id": {
                "type": "integer",
                "description": "ID CropPlana čiji višak objavljujemo (iz get_livestock_status usjevi)"
            },
            "cijena_eur_t": {
                "type": "number",
                "description": "Cijena u EUR po toni (OPG postavlja)"
            },
            "napomena": {
                "type": "string",
                "description": "Napomena za listing (opcionalno)"
            }
        },
        "required": ["crop_plan_id"]
    }
}

# handler — prolazi kroz AIGate:
def _create_futures_listing(params, user, company):
    from superadmin_ai.services import AIGate
    gate = AIGate()
    result = gate.check(
        company=company,
        module='marketplace',
        action_type='create_futures_listing',
        user=user,
        description=f'AI želi kreirati FuturesListing za crop_plan_id={params.get("crop_plan_id")}',
    )
    if result.blocked:
        return {'error': result.message, 'blocked': True}
    if result.queued:
        return {
            'status': 'QUEUED',
            'message': 'Zahtjev je poslan na odobrenje. Potvrdi u AI Cockpitu.',
            'pending_action_id': str(result.pending_action.id) if result.pending_action else None,
        }
    # AUTONOMOUS — izvrši odmah
    try:
        from livestock.models import CropPlan
        from intelligence.services import create_futures_listing_from_crop
        plan = CropPlan.objects.get(pk=params['crop_plan_id'], company=company)
        if params.get('cijena_eur_t'):
            plan._override_price = params['cijena_eur_t']
        created = create_futures_listing_from_crop(plan)
        return {
            'status': 'CREATED' if created else 'ALREADY_EXISTS',
            'kultura': plan.get_kultura_display(),
            'visak_t': float(plan.procijenjeni_višak_t) if plan.procijenjeni_višak_t else None,
        }
    except Exception as e:
        return {'error': str(e)}
```

#### Alat 4: `get_compliance_warnings`
```python
# tools.py definicija:
{
    "name": "get_compliance_warnings",
    "description": "Prediktivna compliance provjera: PDV granica, istekli dokumenti vozila/vozača, membership expiry, karencija goveda, EU fond rokovi. AI upozorava PRIJE problema.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kategorija": {
                "type": "string",
                "description": "Kategorija: sve, pdv, dokumenti, clanarine, livestock, fondovi (default: sve)",
                "enum": ["sve", "pdv", "dokumenti", "clanarine", "livestock", "fondovi"]
            }
        }
    }
}

# handler:
def _get_compliance_warnings(params, user, company):
    from django.utils import timezone
    today = timezone.now().date()
    kategorija = params.get('kategorija', 'sve')
    upozorenja = []

    # PDV granica (30k EUR za udruge)
    if kategorija in ('sve', 'pdv'):
        try:
            if getattr(company, 'is_nonprofit', False) or getattr(company, 'business_type', '') in ('udruga',):
                from finance.models import Transaction
                from django.db.models import Sum
                promet = Transaction.objects.filter(
                    company=company, date__year=today.year, direction='income'
                ).aggregate(s=Sum('amount'))['s'] or 0
                if float(promet) > 25000:
                    upozorenja.append({
                        'tip': 'pdv_granica',
                        'razina': 'warning' if float(promet) < 28000 else 'critical',
                        'poruka': f'Promet {promet:.0f} EUR — granica za PDV obveznika je 30.000 EUR',
                        'akcija': 'Konzultirajte poreznog savjetnika',
                    })
        except Exception:
            pass

    # Istekli dokumenti vozila/vozača
    if kategorija in ('sve', 'dokumenti'):
        try:
            from delivery.models import VehicleDocument, DriverDocument
            vd = VehicleDocument.objects.filter(
                vehicle__company=company,
                valid_until__lte=today + timezone.timedelta(days=30)
            ).order_by('valid_until')[:5]
            for d in vd:
                upozorenja.append({
                    'tip': 'dokument_vozila',
                    'razina': 'critical' if d.is_expired else 'warning',
                    'poruka': f'{d.vehicle.plate_number}: {d.get_doc_type_display()} ističe {d.valid_until}',
                    'preostalo_dana': d.days_until_expiry,
                })
        except Exception:
            pass

    # Membership expiry (udruge)
    if kategorija in ('sve', 'clanarine'):
        try:
            from udruge.models import Clan
            uskoro = Clan.objects.filter(
                company=company, status='aktivan',
                membership_expires__lte=today + timezone.timedelta(days=14),
                membership_expires__gte=today,
            ).count()
            if uskoro:
                upozorenja.append({
                    'tip': 'clanstvo_istice',
                    'razina': 'warning',
                    'poruka': f'{uskoro} članova ima clanstvo koje istice za 14 dana',
                    'akcija': 'Pošalji WhatsApp podsjetnik (send_expiry_reminders)',
                })
        except Exception:
            pass

    # Karencija goveda
    if kategorija in ('sve', 'livestock'):
        try:
            from livestock.models import HealthRecord
            karencija = HealthRecord.objects.filter(
                animal__company=company,
                karencija_do__gte=today,
            ).count()
            if karencija:
                upozorenja.append({
                    'tip': 'karencija_goveda',
                    'razina': 'critical',
                    'poruka': f'{karencija} grla u karenciji — mlijeko i meso NE smiju u prodaju!',
                    'akcija': 'Provjeri ear tagove u livestock modulu',
                })
        except Exception:
            pass

    # Fondovi koji uskoro ističu
    if kategorija in ('sve', 'fondovi'):
        try:
            from intelligence.models import FundOpportunity
            hitni = FundOpportunity.objects.filter(
                status='aktivan',
                rok_prijave__lte=today + timezone.timedelta(days=14),
                rok_prijave__gte=today,
            ).count()
            if hitni:
                upozorenja.append({
                    'tip': 'fond_rok',
                    'razina': 'warning',
                    'poruka': f'{hitni} natječaj/a ističe za 14 dana',
                    'akcija': 'Provjeri get_fund_opportunities za detalje',
                })
        except Exception:
            pass

    return {
        'ukupno_upozorenja': len(upozorenja),
        'status': 'CLEAN' if not upozorenja else ('CRITICAL' if any(u['razina'] == 'critical' for u in upozorenja) else 'WARNING'),
        'upozorenja': upozorenja,
        'firma': company.name,
    }
```

---

## Dio B — Kontekstualni bridge (USER → COMPANY → ALATI)

Problem koji Sonnet identificirao: AI ne zna automatski da Šeki = Uvijek Friškom.

Pročitaj:
```bash
grep -n "company\|user\|context\|company_id" /var/www/fina-connect/ai_assistant/views.py | head -30
grep -n "get_user_company\|session\|company_id" /var/www/fina-connect/core/company_utils.py | head -20
```

Provjeri kako views.py dohvaća company za chat. Ako ne postoji — dodaj u chat view:

```python
# U ai_assistant/views.py, unutar chat view funkcije,
# PRIJE poziva chat_with_claude(), dodaj kontekst u SYSTEM_PROMPT:

def _build_contextual_system_prompt(user, company):
    """Proširuje SYSTEM_PROMPT s kontekstom korisnika i firme."""
    from ai_assistant.claude_client import SYSTEM_PROMPT
    if not company:
        return SYSTEM_PROMPT

    biz_type = getattr(company, 'business_type', '')
    biz_labels = {
        'opg': 'OPG (Obiteljsko poljoprivredno gospodarstvo)',
        'udruga': 'Udruga',
        'doo': 'd.o.o.',
        'obrt': 'Obrt',
    }

    ctx = f"""

## Kontekst trenutnog korisnika
- Ime: {user.get_full_name() or user.username}
- Firma: {company.name}
- Tip: {biz_labels.get(biz_type, biz_type)}
- OIB: {company.oib}
- Država: {getattr(company, 'country', 'HR')}
"""

    # OPG context
    if biz_type == 'opg':
        try:
            from livestock.models import Livestock, CropPlan
            grla = Livestock.objects.filter(company=company).count()
            planovi = CropPlan.objects.filter(company=company, godina__gte=2026).count()
            ctx += f"- Farma: {grla} grla goveda, {planovi} aktivnih planova sjetve\n"
        except Exception:
            pass

    # Intelligence context
    try:
        from intelligence.models import IntelligenceResult, FundOpportunity
        from django.utils import timezone
        novi = IntelligenceResult.objects.filter(
            job__company=company, status='novo'
        ).count()
        fondovi = FundOpportunity.objects.filter(
            status='aktivan',
            rok_prijave__gte=timezone.now().date()
        ).count()
        if novi or fondovi:
            ctx += f"- Intelligence: {novi} novih pronalazaka, {fondovi} aktivnih natječaja\n"
    except Exception:
        pass

    return SYSTEM_PROMPT + ctx
```

Pozovi ovu funkciju umjesto direktnog `SYSTEM_PROMPT` u chat view.

---

## Dio C — Proširenje SYSTEM_PROMPT za nove alate

U `ai_assistant/claude_client.py`, u `SYSTEM_PROMPT` dodaj sekciju:

```python
# Dodaj na kraj SYSTEM_PROMPT (nakon ## Pravila):

"""
## Novi alati — kada ih koristiti

**get_fund_opportunities**: Koristi kad korisnik pita o fondovima, poticajima, subvencijama, 
natječajima, APPRRR, eKohezija, EU novcu. Ne čekaj da te pitaju — ako vidiš da je OPG, proaktivno ponudi.

**get_livestock_status**: Koristi za OPG korisnike kad pitaju o stoci, kravama, mlijeku, 
telenjem, usjEvima, kukuruzu, djetelini, bio certifikaciji.

**create_futures_listing**: Ponudi kad `get_livestock_status` pokaže `auto_listing_spreman: true`.
Uvijek pitaj za potvrdu — ovo mijenja podatke (ASSISTED razina, čeka odobrenje).

**get_compliance_warnings**: Pozovi automatski na početku svake jutarnje sesije (if morning hours).
Ako postoje kritična upozorenja — navedi ih odmah, bez čekanja.
"""
```

---

## Dio D — Registracija u tool_handlers.py

```python
# U handle_tool_call() dispatch rječnik dodaj:
"get_fund_opportunities": _get_fund_opportunities,
"get_livestock_status": _get_livestock_status,
"create_futures_listing": _create_futures_listing,
"get_compliance_warnings": _get_compliance_warnings,
```

---

## Korak: Provjera i testovi

```bash
cd /var/www/fina-connect

# 1. Syntax check
venv/bin/python -c "from ai_assistant.tools import TOOLS; print('Tools:', len(TOOLS))"
venv/bin/python -c "from ai_assistant.tool_handlers import handle_tool_call; print('Handlers OK')"

# 2. Provjeri broj alata (treba biti 25 = 21 + 4 nova)
venv/bin/python -c "
from ai_assistant.tools import TOOLS
print('Ukupno alata:', len(TOOLS))
for t in TOOLS:
    print(' ', t['name'])
"

# 3. Test get_compliance_warnings (fallback ako intelligence nije instaliran)
venv/bin/python manage.py shell -c "
from companies.models import Company
from ai_assistant.tool_handlers import handle_tool_call
from django.contrib.auth import get_user_model
User = get_user_model()

company = Company.objects.filter(name__icontains='Kruljac').first()
user = User.objects.filter(is_superuser=True).first()
result = handle_tool_call('get_compliance_warnings', {'kategorija': 'sve'}, user, company)
import json
print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
"

# 4. Test get_fund_opportunities (bez intelligence app — mora gracefully fallback)
venv/bin/python manage.py shell -c "
from companies.models import Company
from ai_assistant.tool_handlers import handle_tool_call
from django.contrib.auth import get_user_model
User = get_user_model()

company = Company.objects.filter(name__icontains='Kruljac').first()
user = User.objects.filter(is_superuser=True).first()
result = handle_tool_call('get_fund_opportunities', {'tip': 'sve', 'rok_dana': 90}, user, company)
import json
print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
"

# 5. Django check
venv/bin/python manage.py check
```

---

## Tvoje slobodne ruke — CC Code prijedlozi

**Sonnet te eksplicitno poziva da dodaš vlastite opservacije i prijedloge.**

Konkretno: dok čitaš `tools.py` i `tool_handlers.py`, možeš primijetiti:

1. Postoje li handleri koji su nepotpuni ili vraćaju grešku za postojeće module?
2. Postoje li alati koji nedostaju a logično bi trebali biti tu (npr. za transport, udruge, arhivu)?
3. Je li SYSTEM_PROMPT u `claude_client.py` zastarjen za nove module?

Ako primijetiš — **dodaj, ne čekaj instrukciju**. Svaki alat koji dobaš dok čitaš kod je dobrodošao.
Format za vlastite alate: isti pattern kao gore + komentar `# CC Code prijedlog: razlog dodavanja`.

---

## Ažuriraj FENIX_STATUS.md na kraju

```
### AI Tools proširenje v2
- get_fund_opportunities (Intelligence → AI widget) — DONE
- get_livestock_status (Livestock → AI widget) — DONE
- create_futures_listing (ASSISTED, AIGate) — DONE
- get_compliance_warnings (prediktivni, svi moduli) — DONE
- Kontekstualni bridge user→company→tools — DONE
- SYSTEM_PROMPT proširen za nove alate — DONE
```

## Definicija DONE
- [ ] 4+ nova alata u tools.py (25+ ukupno)
- [ ] 4+ handlera u tool_handlers.py
- [ ] handle_tool_call dispatch ažuriran
- [ ] _build_contextual_system_prompt implementiran
- [ ] SYSTEM_PROMPT proširen
- [ ] Svi testovi prolaze bez crasheva (graceful fallback za neinstalirane module)
- [ ] CC Code vlastiti prijedlozi — barem 1 dodatni alat
- [ ] django check: 0 grešaka
- [ ] /tmp/intelligence_v2_done.txt
