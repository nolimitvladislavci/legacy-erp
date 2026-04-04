# CC_TASK — INFORMACIJSKI POSREDNIK + FINA BONITET INTEGRACIJA
# Agent: Claude Code
# Prioritet: KRITIČAN — Strateški, Zakon NN 89/25
# Datum: 2026-03-24
# Status: ČEKA GEMINIJEV ARHITEKTONSKI PREGLED + IVANOV ENTER
#
# ════════════════════════════════════════════════════════════════
# VETO PROTOKOL (Gemini): Kod ne ide u produkciju bez:
#   1. Pregleda ovog taska od strane Geminija i Sonetta
#   2. Ivanovog odobravanja (ENTER)
#   3. Verifikacije da su svi preduvjeti ispunjeni (vidi PREFLIGHT)
# ════════════════════════════════════════════════════════════════

## KONTEKST — zašto je ovo strateški prioritet

Zakon o fiskalizaciji NN 89/25 (na snazi od 01.09.2025) uveo je kategoriju
"Informacijski posrednik" — pravna ili fizička osoba koja klijentima pruža:
  - Kreiranje, slanje i primanje eRačuna (B2B obligatorno od 01.01.2026)
  - Fiskalizacija eRačuna prema Poreznoj upravi
  - eIzvještavanje (naplatni podaci do 20. u mjesecu)
  - Metapodatkovna usluga (AMS — Adresat Metapodatkovni Servis)

Status posrednika = klijent nas ovlašćuje 1 klik u FiskAplikaciji.
Rok koji je prošao (31.12.2025) znači: svi klijenti koji nisu izabrali
posrednika su u prekršaju. Mi nudimo rješenje.

eracun/ app VEĆ POSTOJI s: posrednik_service.py, validator.py (lxml XSD),
tasks.py (Celery), UBL generator, ZUGFeRD, XRechnung.
Infrastruktura je 80% gotova. Ovaj task dodaje preostalih 20%.

## PREFLIGHT — provjeri PRIJE IJEDNOG REDA KODA

```bash
# 1. Struktura certs/ direktorija
ls -la /var/www/fina-connect/certs/
# Očekivano: fina_cert.p12, konjik-doo-fina-certifikat-*.p12, CA pem fajlovi

# 2. Permissions — PROBLEM: trenutno 0775 claude:claude — MORA biti 0400 www-data:www-data
stat /var/www/fina-connect/certs/fina_cert.p12

# 3. eRačun app status
python manage.py showmigrations eracun | tail -5

# 4. XSD schema postoji?
ls /var/www/fina-connect/eracun/xsd/

# 5. Celery worker živi?
systemctl is-active celery-worker

# 6. Company model — postoji li has_signed_tc_consent?
python manage.py shell -c "from companies.models import Company; print([f.name for f in Company._meta.concrete_fields])" | grep -o "consent\|tc_sign\|gdpr"
```

Ako preflight pokazuje probleme — STANI. Prijavi Sonnetu. Ne nastavljaj.

## ZADATAK 1 — Sigurnost certifikata (KRITIČNO — radi PRVO)

### Problem koji postoji
/var/www/fina-connect/certs/ je:
- vlasnik: claude:claude (POGREŠNO — treba www-data:www-data)
- dozvole: 0775 (POGREŠNO — treba 0400 za p12, 0444 za pem)
- NGINX može servirati sadržaj iz /var/www/ — RIZIK

### Rješenje

```bash
# Premjesti certs van web roota u sigurnu lokaciju
mkdir -p /etc/limit-connect/certs
cp /var/www/fina-connect/certs/*.p12 /etc/limit-connect/certs/
cp /var/www/fina-connect/certs/*.pem /etc/limit-connect/certs/
cp /var/www/fina-connect/certs/.cert_password /etc/limit-connect/certs/

# Stroge dozvole
chown -R www-data:www-data /etc/limit-connect/
chmod 700 /etc/limit-connect/certs/
chmod 400 /etc/limit-connect/certs/*.p12
chmod 444 /etc/limit-connect/certs/*.pem
chmod 400 /etc/limit-connect/certs/.cert_password

# Provjera — nginx NE SMI servirati ovo
ls -la /etc/limit-connect/certs/
```

### Django settings — referenca na novu lokaciju
U core/settings.py dodaj:
```python
# Certifikati — IZVAN web roota
FINA_CERTS_DIR = '/etc/limit-connect/certs/'
FINA_CERT_P12 = os.path.join(FINA_CERTS_DIR, 'fina_cert.p12')
FINA_CA_BUNDLE = os.path.join(FINA_CERTS_DIR, 'fina_ca_bundle.pem')
# Lozinka se čita iz fajla, nikad nije hardcodana
FINA_CERT_PASSWORD = open(os.path.join(FINA_CERTS_DIR, '.cert_password')).read().strip()
```

### ERacunConfig model — cert_p12 polje
PROBLEM: ERacunConfig.cert_p12 je FileField(upload_to='eracun/certs/')
što sprema certifikate u MEDIA_ROOT — to je web-dostupno!

Promjena:
```python
# NE OVAKO:
cert_p12 = models.FileField(upload_to='eracun/certs/')

# OVAKO — samo path referenca, fajl je u /etc/limit-connect/certs/
cert_path = models.CharField(
    max_length=500,
    blank=True,
    verbose_name='Putanja do certifikata',
    help_text='Apsolutna putanja: /etc/limit-connect/certs/firma.p12'
)
```

## ZADATAK 2 — Company model: has_signed_tc_consent (GDPR zaštita)

Provjeri postoji li polje. Ako ne postoji, dodaj ga:

```python
# U companies/models.py, klasa Company:
has_signed_tc_consent = models.BooleanField(
    default=False,
    verbose_name='Potpisao T&C (privola GDPR čl.6b)',
    help_text='Mora biti True da bi sustav smio agregirati podatke ove firme.'
)
tc_consent_signed_at = models.DateTimeField(
    null=True, blank=True,
    verbose_name='Datum potpisivanja T&C'
)
tc_consent_version = models.CharField(
    max_length=20, blank=True,
    verbose_name='Verzija T&C (npr. v2.1-2026)'
)
```

Migracija:
```bash
python manage.py makemigrations companies --name="add_tc_consent_gdpr"
python manage.py migrate companies
```

### Decorator za zaštitu svih API poziva prema institucijama

```python
# eracun/decorators.py (NOVI FAJL)
from functools import wraps
from django.core.exceptions import PermissionDenied

def requires_tc_consent(func):
    """
    Sprječava bilo kakvu institucionalnu API komunikaciju
    za firme koje nisu potpisale T&C.
    Primjenjuje se na SVE Celery taskove i servise koji
    komuniciraju s FINA / Poreznom upravom.
    """
    @wraps(func)
    def wrapper(company, *args, **kwargs):
        if not getattr(company, 'has_signed_tc_consent', False):
            raise PermissionDenied(
                f"Firma {company.name} (OIB: {company.oib}) nema potpisane T&C. "
                f"Institucijska komunikacija je blokirana. "
                f"Admin: postavite has_signed_tc_consent=True nakon potpisivanja."
            )
        return func(company, *args, **kwargs)
    return wrapper
```

## ZADATAK 3 — Asinkrono eIzvještavanje (Celery, nikad sync)

### Novi Celery task: submit_eizvjestavanje

```python
# eracun/tasks.py — DODAJ (ne zamjenjuj postojeće):

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=300,   # 5 minuta između pokušaja
    soft_time_limit=180,        # 3 minute max za jedan poziv
    autoretry_for=(requests.exceptions.Timeout,
                   requests.exceptions.ConnectionError),
)
def submit_eizvjestavanje(self, company_id: int, period_month: int, period_year: int):
    """
    Dostavlja eIzvještaj Poreznoj upravi za zadani period.
    Nikad se ne poziva sync — uvijek .delay() ili .apply_async().

    Retry logika:
    - Attempt 1: odmah
    - Attempt 2: 5 min
    - Attempt 3: 5 min
    - Attempt 4: 5 min
    - Attempt 5: 5 min (finalni)
    - Nakon 5 pokušaja: status='failed', WhatsApp alert Ivanu
    """
    from companies.models import Company
    from eracun.services.eizvjestavanje_service import EIzvjestavanjeService
    from eracun.decorators import requires_tc_consent

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        logger.error('submit_eizvjestavanje: Company %s ne postoji', company_id)
        return {'ok': False, 'error': 'Company not found'}

    # GDPR zaštita — bez T&C nema komunikacije
    if not company.has_signed_tc_consent:
        logger.warning('submit_eizvjestavanje: %s nema T&C privolu', company.name)
        return {'ok': False, 'error': 'no_tc_consent'}

    try:
        service = EIzvjestavanjeService(company)
        result = service.submit(period_month=period_month, period_year=period_year)
        logger.info('eIzvještavanje OK: %s %d/%d', company.name, period_month, period_year)
        return result
    except Exception as exc:
        logger.error('eIzvještavanje FAIL: %s — %s', company.name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_fina_bonitet(self, company_id: int, oib_dobavljaca: str):
    """
    Provjerava bonitet dobavljača (BON-1/BON-2) preko FINA javnog API-ja.
    Trigerira se automatski kada klijent unese novi račun.
    FINA javni podaci — ne treba privola za dobavljača (javni registar).
    """
    from companies.models import Company
    from eracun.services.fina_bonitet_service import FinaBonitetService

    try:
        company = Company.objects.get(id=company_id)
        if not company.has_signed_tc_consent:
            return {'ok': False, 'error': 'no_tc_consent'}

        service = FinaBonitetService()
        result = service.check_oib(oib_dobavljaca)

        if result.get('risk_level') in ('high', 'stecaj', 'blokada'):
            # WhatsApp alert klijentu
            from core.whatsapp import send_whatsapp_alert
            send_whatsapp_alert(
                company=company,
                message=f"⚠️ LIMIT Connect upozorenje:\n"
                        f"Dobavljač OIB {oib_dobavljaca} ima status: {result['risk_level']}\n"
                        f"Preporučamo provjeru prije plaćanja."
            )

        return result
    except Exception as exc:
        raise self.retry(exc=exc)
```

## ZADATAK 4 — XSD validacija (nadogradnja postojeće)

Validator POSTOJI u eracun/services/validator.py s lxml. Nadogradnja:

```python
# eracun/services/validator.py — DODAJ uz postojeće:

# HR-specifični XSD (CIUS-HR 2025) — obavezan od 01.01.2026
CIUS_HR_2025_XSD = os.path.join(XSD_DIR, 'CIUS-HR-2025.xsd')

def validate_cius_hr_2025(xml_bytes: bytes) -> tuple[bool, list[str]]:
    """
    Validacija prema HR CIUS 2025 specifikaciji.
    Porezna uprava prihvaća samo:
    urn:cen.eu:en16931:2017#compliant#urn:mfin.gov.hr:cius-2025:1.0
    
    Returns: (is_valid: bool, errors: list[str])
    NIKAD ne šalji XML bez ove validacije.
    """
    errors = []
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        return False, [f'XML parse error: {e}']

    # 1. SpecificationIdentifier provjera
    ns = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
    spec = root.findtext('.//cbc:CustomizationID', namespaces=ns) or ''
    if 'mfin.gov.hr:cius-2025' not in spec:
        errors.append(f'SpecificationIdentifier nije HR CIUS 2025. Nađeno: "{spec}"')

    # 2. OIB provjera (11 znamenki, MOD11-10)
    supplier_oib = root.findtext('.//cbc:CompanyID', namespaces=ns) or ''
    if supplier_oib and not _validate_oib_mod11(supplier_oib):
        errors.append(f'Neispravan OIB izdavatelja: {supplier_oib}')

    # 3. XSD schema validacija
    schema = _get_xsd_schema()
    if schema:
        is_valid = schema.validate(root)
        if not is_valid:
            errors.extend([str(e) for e in schema.error_log])

    return len(errors) == 0, errors


def _validate_oib_mod11(oib: str) -> bool:
    """MOD 11-10 algoritam za OIB validaciju."""
    if not oib.isdigit() or len(oib) != 11:
        return False
    iso = 10
    for digit in oib[:10]:
        iso = (iso + int(digit)) % 10
        iso = iso if iso != 0 else 10
        iso = (iso * 2) % 11
    return (iso + int(oib[10])) % 10 == 1
```

## ZADATAK 5 — FINA Bonitet Servis (NOVI FAJL)

```python
# eracun/services/fina_bonitet_service.py (NOVI FAJL)
"""
FINA Javni Registri — BON-1, BON-2, GFI pregled.
Pravna osnova: Javno dostupni podaci (FINA e-servisi, bez autentikacije za javne).
GDPR: Podaci pravnih osoba, ne fizičkih — ne zahtijeva privolu treće strane.
"""
import requests
import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('eracun.fina_bonitet')

FINA_API_BASE = 'https://sudreg-api.pravosudje.hr/javni/v1'  # Sudski registar (javni)
FINA_BONITET_BASE = 'https://rgfi.fina.hr/IzvjestajiRS-war/rest/rgfi'  # RGFI javni


class FinaBonitetService:
    """
    Provjera boniteta poslovnih subjekata kroz FINA javne registre.

    Što može (LEGALNO, javni podaci):
    - GFI (Godišnji financijski izvještaj) — prihodi, dugovi, kapital
    - Sudski registar — status firme, stečaj, likvidacija
    - Registar blokiranih računa (javno)

    Što NE može (privatno, treba privola):
    - Porezni dugovi konkretne firme
    - Transakcijski podaci
    - Osobni podaci direktora (samo javni registar)
    """

    CACHE_TTL = 3600 * 24  # 24 sata — FINA podaci se ne mijenjaju svaki sat

    def check_oib(self, oib: str) -> dict:
        """
        Kompletna provjera poslovnog subjekta po OIB-u.
        Koristi cache — ista firma se ne pita više puta dnevno.
        """
        cache_key = f'fina_bonitet_{oib}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = {
            'oib': oib,
            'naziv': '',
            'status': 'unknown',
            'risk_level': 'unknown',   # low / medium / high / stecaj / blokada
            'gfi_prihod': None,
            'gfi_dug': None,
            'stecaj': False,
            'blokada_racuna': False,
            'source': 'fina_public',
            'checked_at': None,
        }

        try:
            # 1. Sudski registar — status firme
            sudski = self._check_sudski_registar(oib)
            result.update(sudski)

            # 2. RGFI — financijski izvještaj (zadnja godina)
            gfi = self._check_gfi(oib)
            result.update(gfi)

            # 3. Procjena rizika
            result['risk_level'] = self._calculate_risk(result)

            from django.utils import timezone
            result['checked_at'] = timezone.now().isoformat()

            cache.set(cache_key, result, self.CACHE_TTL)
            return result

        except Exception as e:
            logger.warning('FINA bonitet check failed za %s: %s', oib, e)
            result['error'] = str(e)
            return result

    def _check_sudski_registar(self, oib: str) -> dict:
        """Provjera statusa u sudskom registru (javni API)."""
        try:
            resp = requests.get(
                f'{FINA_API_BASE}/subjekt',
                params={'oib': oib},
                timeout=10,
                headers={'Accept': 'application/json'},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'naziv': data.get('naziv', ''),
                    'status': data.get('statusSubjekta', 'unknown'),
                    'stecaj': data.get('stecaj', False),
                    'vrsta': data.get('vrstaPravnogOblika', ''),
                }
        except Exception as e:
            logger.debug('Sudski registar API error: %s', e)
        return {}

    def _check_gfi(self, oib: str) -> dict:
        """Godišnji financijski izvještaj — zadnja objavljena godina."""
        try:
            resp = requests.get(
                f'{FINA_BONITET_BASE}/podaci',
                params={'oib': oib, 'godina': 2024},
                timeout=10,
                headers={'Accept': 'application/json'},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'gfi_prihod': data.get('ukupniPrihodi'),
                    'gfi_dug': data.get('kratkorocneObveze'),
                }
        except Exception as e:
            logger.debug('RGFI API error: %s', e)
        return {}

    def _calculate_risk(self, data: dict) -> str:
        """Procjena razine rizika iz prikupljenih podataka."""
        if data.get('stecaj'):
            return 'stecaj'
        if data.get('blokada_racuna'):
            return 'blokada'
        status = data.get('status', '').lower()
        if any(x in status for x in ['brisanje', 'likvidac', 'stecaj']):
            return 'high'
        prihod = data.get('gfi_prihod') or 0
        dug = data.get('gfi_dug') or 0
        if prihod > 0 and dug > prihod * 2:
            return 'high'
        if prihod > 0 and dug > prihod:
            return 'medium'
        return 'low'
```

## ZADATAK 6 — EIzvjestavanje Servis (NOVI FAJL)

```python
# eracun/services/eizvjestavanje_service.py (NOVI FAJL)
"""
eIzvještavanje prema Poreznoj upravi — Fiskalizacija 2.0 (NN 89/25).

Pravna osnova: Zakon o fiskalizaciji čl. 31-45.
Bez certifikacije za ERP direktnu integraciju (potvrđeno od PU).
XML format: JSON u REST zahtjevu prema servisu Porezne uprave.
"""
import json
import requests
import logging
from django.conf import settings
from eracun.services.validator import validate_cius_hr_2025

logger = logging.getLogger('eracun.eizvjestavanje')

PU_EIZVJESTAVANJE_URL = 'https://cis.porezna-uprava.hr:8449/FiskalizacijaService'
PU_EIZVJESTAVANJE_TEST_URL = 'https://cistest.apis-it.hr:8449/FiskalizacijaService'


class EIzvjestavanjeService:
    """
    Slanje eIzvještaja Poreznoj upravi.

    Obavezno od 01.01.2026. za sve obveznike fiskalizacije.
    Rok: do 20. u mjesecu za prethodni mjesec.
    """

    def __init__(self, company):
        self.company = company
        self.test_mode = getattr(settings, 'EIZVJESTAVANJE_TEST_MODE', True)
        self.base_url = PU_EIZVJESTAVANJE_TEST_URL if self.test_mode else PU_EIZVJESTAVANJE_URL

    def submit(self, period_month: int, period_year: int) -> dict:
        """
        Slanje eIzvještaja za zadani period.
        Validacija → Priprema XML → XSD provjera → Slanje → Log.
        """
        from eracun.models import ERacun

        if not self.company.has_signed_tc_consent:
            raise PermissionError('Firma nema potpisane T&C — blokada.')

        # Dohvati naplaćene eRačune za period
        racuni = ERacun.objects.filter(
            company=self.company,
            issue_date__year=period_year,
            issue_date__month=period_month,
            status__in=['accepted', 'paid'],
        )

        if not racuni.exists():
            logger.info('Nema eRačuna za %s %d/%d', self.company.name, period_month, period_year)
            return {'ok': True, 'submitted': 0, 'message': 'Nema podataka za period'}

        # Pripremi XML payload
        xml_payload = self._build_xml(racuni, period_month, period_year)

        # XSD validacija PRIJE slanja
        is_valid, errors = validate_cius_hr_2025(xml_payload)
        if not is_valid:
            logger.error('XSD validacija failed za %s: %s', self.company.name, errors)
            return {'ok': False, 'errors': errors, 'submitted': 0}

        # Slanje s certifikatom
        try:
            cert_path = self._get_cert_path()
            resp = requests.post(
                f'{self.base_url}/eIzvjestavanje',
                data=xml_payload,
                headers={'Content-Type': 'application/xml'},
                cert=cert_path,
                verify=settings.FINA_CA_BUNDLE,
                timeout=30,
            )
            resp.raise_for_status()

            logger.info(
                'eIzvještavanje OK: %s %d/%d — %d računa',
                self.company.name, period_month, period_year, racuni.count()
            )
            return {'ok': True, 'submitted': racuni.count(), 'status_code': resp.status_code}

        except requests.exceptions.HTTPError as e:
            logger.error('PU HTTP error za %s: %s', self.company.name, e)
            return {'ok': False, 'error': str(e), 'submitted': 0}

    def _get_cert_path(self):
        """Dohvati putanju certifikata iz sigurne lokacije."""
        import os
        certs_dir = getattr(settings, 'FINA_CERTS_DIR', '/etc/limit-connect/certs/')
        # Svaka firma ima vlastiti certifikat ili koristimo globalni
        company_cert = os.path.join(certs_dir, f'{self.company.oib}.p12')
        if os.path.exists(company_cert):
            return company_cert
        return getattr(settings, 'FINA_CERT_P12', os.path.join(certs_dir, 'fina_cert.p12'))

    def _build_xml(self, racuni, month: int, year: int) -> bytes:
        """Gradi XML payload za eIzvještavanje."""
        # Placeholder — UBL generator već postoji u ubl_generator.py
        # Integrirati s postojećim generatorom
        raise NotImplementedError(
            'Implementirati u suradnji s ubl_generator.py. '
            'Pogledaj Tehničku specifikaciju Porezne uprave.'
        )
```

## ZADATAK 7 — Integracija s Knowledge Graph (FINA → RegulatoryUpdate)

```python
# eracun/services/fina_knowledge_ingestion.py (NOVI FAJL)
"""
Integracija FINA bonitet podataka u Knowledge Graph (limit_connect_ai).
Kad sustav otkrije dobavljača s visokim rizikom, stvara LegalOpportunity
tipa 'compliance_alert' za tu firmu.
"""

def ingest_supplier_risk_to_knowledge_graph(company, supplier_oib: str, bonitet_result: dict):
    """
    Ako dobavljač ima visoki rizik — stvori CompanyOpportunityMatch upozorenje.
    Ovo je spoj između eRačun modula i Knowledge Graph-a.
    """
    from limit_connect_ai.models_knowledge_graph import (
        LegalOpportunity, ClientOpportunityMatch
    )

    if bonitet_result.get('risk_level') not in ('high', 'stecaj', 'blokada'):
        return

    # Dohvati ili stvori LegalOpportunity za "dobavljač pred stečajem"
    opp, _ = LegalOpportunity.objects.get_or_create(
        opportunity_type='other',
        name=f'Upozorenje: Dobavljač OIB {supplier_oib}',
        defaults={
            'description': (
                f"FINA bonitet provjera pokazuje: {bonitet_result.get('risk_level')}. "
                f"Naziv: {bonitet_result.get('naziv', 'N/A')}. "
                f"Preporuča se oprez pri plaćanju."
            ),
            'risk_level': 'high',
            'confidence_score': 0.95,
            'is_active': True,
            'source_reference': 'FINA Javni registar',
        }
    )

    ClientOpportunityMatch.objects.update_or_create(
        company=company,
        opportunity=opp,
        defaults={
            'status': 'identified',
            'calculated_savings': 0,
            'calculation_details': bonitet_result,
        }
    )
```

## ZADATAK 8 — Migracije i testovi

### Migracije (u redoslijedu)
```bash
# 1. Sigurnost certifikata — bash (ne migration)
# 2. Company model
python manage.py makemigrations companies --name="add_tc_consent_gdpr"
python manage.py migrate companies
# 3. Provjera eRačun migracija
python manage.py showmigrations eracun
# 4. Ako ERacunConfig.cert_p12 treba migrirati na cert_path:
python manage.py makemigrations eracun --name="cert_path_secure_migration"
python manage.py migrate eracun
```

### Testovi (minimum 15)
Napiši u eracun/tests/test_posrednik_integration.py:

```python
# Test lista (implementiraj sve):
# 1. test_cert_permissions_correct() — certs su 0400 www-data
# 2. test_cert_not_in_web_root() — /etc/limit-connect/ nije dostupan kroz nginx
# 3. test_tc_consent_blocks_api_call() — bez privole → PermissionError
# 4. test_tc_consent_allows_api_call() — s privolom → prolaz
# 5. test_oib_mod11_valid() — ispravan OIB prolazi
# 6. test_oib_mod11_invalid() — krivi OIB pada XSD
# 7. test_xsd_validation_valid_xml() — ispravan UBL prolazi
# 8. test_xsd_validation_invalid_xml() — neispravan UBL pada
# 9. test_cius_hr_2025_spec_id() — krivi SpecificationIdentifier pada
# 10. test_celery_task_retry_on_timeout() — Timeout → retry
# 11. test_celery_task_max_retries_alert() — nakon 5 pokušaja → alert
# 12. test_fina_bonitet_cache() — isti OIB drugi put ide iz cachea
# 13. test_bonitet_stecaj_risk_level() — stečaj → 'stecaj' risk
# 14. test_bonitet_triggers_knowledge_graph() — visoki rizik → ClientOpportunityMatch
# 15. test_eizvjestavanje_blocked_without_consent() — blokada bez T&C
# 16. test_eizvjestavanje_async_not_sync() — submit_eizvjestavanje.delay() prolazi
```

## DONE KRITERIJ

Zadatak je gotov kada:
- [ ] /etc/limit-connect/certs/ postoji, 0400, www-data:www-data
- [ ] Niti jedan cert nije u /var/www/ ili media/
- [ ] Company.has_signed_tc_consent polje postoji i migracija je prošla
- [ ] @requires_tc_consent decorator blokira API bez privole
- [ ] submit_eizvjestavanje Celery task s retry logikom
- [ ] validate_cius_hr_2025() vraća (bool, list[str])
- [ ] FinaBonitetService.check_oib() radi na test OIB-u
- [ ] check_fina_bonitet Celery task trigerira WhatsApp alert za 'high' rizik
- [ ] 15+ testova zeleno
- [ ] Nema niti jednog sync HTTP poziva prema državnim serverima (sve kroz Celery)
- [ ] git commit s jasnom porukom

## APSOLUTNE ZABRANE (ne kršiti ni u jednoj okolnosti)

1. NIKAD ne spajati sync Gunicorn request s državnim API pozivom
2. NIKAD ne pisati certifikate u /var/www/, /media/, /static/
3. NIKAD ne pristupati institucijskim podacima bez has_signed_tc_consent=True
4. NIKAD ne hardcodati lozinke certifikata u kod — uvijek iz fajla
5. NIKAD ne slati XML bez XSD validacije prema Poreznoj upravi
6. NIKAD ne agregirati podatke trećih osoba bez njihove privole (GDPR)

## NAPOMENA ZA GEMINI REVIEW

Ovaj task čeka Geminijev arhitektonski pregled i Ivanov ENTER.
Gemini treba verificirati:
- Je li model za eIzvještavanje konzistentan s Knowledge Graph modelima?
- Nedostaje li kakva veza između EIzvjestavanjeService i RegulatoryUpdate?
- Je li FINA bonitet integracija u Knowledge Graph semantički ispravna?

Tek nakon Geminijinog "OK" i Ivanovog "ENTER" → CC Code implementira.
