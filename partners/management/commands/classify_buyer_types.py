"""
Smart Buyer Type klasifikacija — 33K partnera.

Logika prioriteta (prvi match pobjeđuje):
  1. INOZEMSTVO  — country nije HR/Hrvatska, ili EU VAT prefix u OIB-u
  2. B2G         — ključne riječi proračunskih korisnika
  3. UDRUGA      — ključne riječi neprofitnih organizacija
  4. B2B         — d.o.o., j.d.o.o., d.d., obrt, OPG, itd.
  5. B2C         — sve ostalo (fizičke osobe)

Svaki partner dobiva:
  - buyer_type (b2g, b2b_vat, b2b_novat, udruga_vat, udruga_novat, inozemstvo, b2c)
  - is_budget_user = True za B2G
  - is_nonprofit_no_activity = True za udruge bez PDV-a
  - needs_verification polje u notes ako regex nije 100% siguran

Pokretanje:
  python manage.py classify_buyer_types --dry-run     # samo statistika
  python manage.py classify_buyer_types               # produkcijski run
  python manage.py classify_buyer_types --company 5   # samo jedna firma
"""

import re
from contextlib import nullcontext
from django.core.management.base import BaseCommand
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone

from partners.models import Partner
from django.core.exceptions import ObjectDoesNotExist


# ═══════════════════════════════════════════════════════
# REGEX OBRASCI
# ═══════════════════════════════════════════════════════

HR_COUNTRIES = {'HR', 'Hrvatska', 'HRVATSKA', 'hrvatska', ''}

EU_VAT_PREFIXES = (
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES',
    'FI', 'FR', 'GB', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
)

# B2G — proračunski korisnici
B2G_PATTERNS = re.compile(
    r'\b('
    r'OPĆINA|OPCINA|GRAD\s|GRADA\s|GRADSKA\s|GRADSKI\s|'
    r'ŠKOLA|SKOLA|OSNOVNA\sŠKOLA|SREDNJA\sŠKOLA|'
    r'BOLNICA|KLINIK|'
    r'MINISTARST|'
    r'SVEUČILIŠT|SVEUCILIS|FAKULTET|'
    r'VRTIĆ|VRTIC|DJEČJI\sVRTIĆ|'
    r'ZAVOD\s|NASTAVNI\sZAVOD|'
    r'DRŽAVN|DRZAVN|'
    r'AGENCIJA\sZA|'
    r'URED\s|'
    r'FOND\sZA|FONDOV|'
    r'CENTAR\sZA\sSOC|'
    r'TURISTIČKA\sZAJEDNICA|TURISTICKA\sZAJEDNICA|'
    r'ŽUPANIJ|ZUPANIJ|'
    r'POREZNA\sUPRAVA|'
    r'INSPEKTORAT|'
    r'JAVNI\sBILJEŽNIK|JAVNI\sBILJEZNIK|'
    r'REGOS|HZZO|HZMO|HZZ\b|FINA\b|'
    r'PRORAČUN|PRORACUN|'
    r'HRVATSKI\sSABOR|VLADA\sRH|PREDSJEDNIK'
    r')\b',
    re.IGNORECASE | re.UNICODE,
)

# Podrasci unutar B2G koji su zapravo B2B (slobodna zanimanja, komunalna poduzeća)
B2G_ACTUALLY_B2B = re.compile(
    r'('
    r'JAVNI\s+BILJEŽNIK|JAVNI\s+BILJEŽNICA|JAVNI\s+BILJEZNIK|'
    r'VODOVOD|KOMUNALN|PLINARA|'
    r'URED\s+OVLAŠTENOG|URED\s+OVLASTENOG'
    r')',
    re.IGNORECASE | re.UNICODE,
)

# Stroga pravna forma — D.O.O., J.D.O.O., D.D., obrt, VL., GmbH itd.
# Ovo NIJE isto što i B2B_PATTERNS koji uključuje i "AGENCIJA", "TRANS" itd.
LEGAL_FORM_RE = re.compile(
    r'('
    r'\bD\.O\.O\.?\b|\bD\.O\.O\b|'
    r'\bJ\.D\.O\.O\.?\b|\bJ\.D\.O\.O\b|'
    r'\bD\.D\.?\b|'
    r'\bK\.D\.?\b|'
    r'\bD\.N\.O\.?\b|'
    r'\bOBRT\b|\bVL\.\s|'
    r'\bGMBH\b|\bS\.R\.L\b|'
    r'\bB\.V\.\b|\bN\.V\.\b|'
    r'\bLTD\b|\bINC\b|\bCORP\b'
    r')',
    re.IGNORECASE | re.UNICODE,
)

# UDRUGE / neprofitne
NONPROFIT_PATTERNS = re.compile(
    r'\b('
    r'UDRUGA|ZAKLADA|'
    r'KUD\s|KULTURNO\sUMJETNIČKO|'
    r'SINDIKAT|'
    r'SPORTSK|NOGOMETNI\sKLUB|NK\s|FK\s|HNK\s|ŠNK\s|'
    r'CRVENI\sKRIŽ|CRVENI\sKRIZ|CARITAS|'
    r'HUMANITARN|'
    r'ZAJEDNICA\sRAČ|ZAJEDNICA\sRAC|'
    r'VATROGASN|DVD\s|'
    r'LOVAČK|LOVACK|RIBOLOV|'
    r'STRANKA\s|SDP\b|HDZ\b|'
    r'SAVEZ\s|'
    r'ORGANIZACIJ|'
    r'DOBROVOLJ'
    r')',
    re.IGNORECASE | re.UNICODE,
)

# B2B — gospodarski subjekti (široki match za korak 4)
B2B_PATTERNS = re.compile(
    r'('
    r'\bD\.O\.O\.?\b|\bD\.O\.O\b|'
    r'\bJ\.D\.O\.O\.?\b|\bJ\.D\.O\.O\b|'
    r'\bD\.D\.?\b|'
    r'\bK\.D\.?\b|'
    r'\bD\.N\.O\.?\b|'
    r'\bOBRT\b|\bVL\.\s|'
    r'\bOPG\s|\bO\.P\.G\.\s|\bP\.G\.\s|'
    r'\bTRGOVINA\s|\bSERVIS\s|'
    r'\bAUTOŠKOLA\b|\bAUTOSKOLA\b|'
    r'\bAGENCIJA\b|'
    r'\bTRANS\b|\bTRANSPORT|'
    r'\bCOMMERCE\b|\bTRADE\b|\bGROUP\b|\bGRUPA\b|'
    r'\bCONSULTING\b|\bINŽENJERING\b|\bINZENJERING\b|'
    r'\bGMBH\b|\bS\.R\.L\b|\bKG\b|'
    r'\bB\.V\.\b|\bN\.V\.\b|'
    r'\bLTD\b|\bINC\b|\bCORP\b|'
    r'\bTVRTKA\b|'
    r'\bZADRUGA\b|'
    r'\bVODOVOD\b|\bKOMUNALN|\bPLINARA\b'
    r')',
    re.IGNORECASE | re.UNICODE,
)

# Synesis "lažni" OIB-ovi
SYNESIS_FAKE_RE = re.compile(r'^SYN-|^---$|^--\*--$|^\d{1,7}$')

# Tehnički zapisi (konti, ne pravi partneri)
TECHNICAL_PATTERNS = re.compile(
    r'^('
    r'AMORTIZACIJA|KUPCI\sGRAĐANI|KUPCI\sGRADJANI|'
    r'POREZ\sNA|RASHOD|PRIHOD|'
    r'ZAKUP\sZEMLJIŠTA|ZAKUP\sZEMLJISTA|'
    r'TEČAJNE\sRAZLIKE|TECAJNE\sRAZLIKE|'
    r'POČETNO\sSTANJE|POCETNO\sSTANJE|'
    r'PRIJENOS\sSALDA|'
    r'ZAKLJUČAK|ZAKLJUCAK|'
    r'CONSORTIUM|KOMPENZACIJ'
    r')',
    re.IGNORECASE | re.UNICODE,
)


def is_valid_hr_oib(oib: str) -> bool:
    """Provjera kontrolne znamenke HR OIB-a (ISO 7064 MOD 11,10)."""
    if not oib or len(oib) != 11 or not oib.isdigit():
        return False
    remainder = 10
    for digit in oib[:10]:
        remainder = (remainder + int(digit)) % 10
        if remainder == 0:
            remainder = 10
        remainder = (remainder * 2) % 11
    check = 11 - remainder
    if check == 10:
        check = 0
    return check == int(oib[10])


def classify_partner(partner) -> dict:
    """
    Klasificira jednog partnera. Vraća dict s:
      buyer_type, is_budget_user, is_nonprofit_no_activity,
      confidence (high/medium/low), reason
    """
    name = (partner.name or '').strip().upper()
    oib = (partner.oib or '').strip()
    country = (partner.country or '').strip()

    result = {
        'buyer_type': 'b2c',
        'is_budget_user': False,
        'is_nonprofit_no_activity': False,
        'confidence': 'high',
        'reason': 'Default: fizička osoba (B2C)',
    }

    has_legal_form = bool(LEGAL_FORM_RE.search(name))
    has_b2b_match = bool(B2B_PATTERNS.search(name))

    # ── 0. Tehnički zapisi — ne diraj ──
    if TECHNICAL_PATTERNS.match(name) or (SYNESIS_FAKE_RE.match(oib) and not name):
        result['reason'] = 'Tehnički zapis / konto — preskočen'
        result['confidence'] = 'skip'
        return result

    # ── 1. INOZEMSTVO ──
    is_foreign_country = country not in HR_COUNTRIES
    has_eu_vat = any(oib.upper().startswith(p) for p in EU_VAT_PREFIXES) if oib else False

    if is_foreign_country or has_eu_vat:
        result['buyer_type'] = 'inozemstvo'
        result['is_budget_user'] = False
        if is_foreign_country:
            result['reason'] = f'Inozemstvo: country={country}'
        else:
            result['reason'] = f'Inozemstvo: EU VAT prefix u OIB-u ({oib[:2]})'
        result['confidence'] = 'high'
        return result

    # ── 2. B2G — proračunski korisnici ──
    b2g_match = B2G_PATTERNS.search(name)
    if b2g_match:
        match_word = b2g_match.group(0)

        # IZNIMKA 1: Javni bilježnici, uredi ovlaštenih inženjera = slobodna zanimanja
        if B2G_ACTUALLY_B2B.search(name):
            result['buyer_type'] = 'b2b_novat'
            result['is_budget_user'] = False
            reason_map = {
                'BILJEŽNIK': 'Javni bilježnik (slobodno zanimanje)',
                'BILJEZNIK': 'Javni bilježnik (slobodno zanimanje)',
                'VODOVOD': 'Komunalno poduzeće',
                'KOMUNALN': 'Komunalno poduzeće',
                'PLINARA': 'Komunalno poduzeće',
                'OVLAŠTENOG': 'Ured ovlaštenog inženjera (slobodno zanimanje)',
                'OVLASTENOG': 'Ured ovlaštenog inženjera (slobodno zanimanje)',
            }
            detail = 'Nije proračun'
            for kw, desc in reason_map.items():
                if kw in name:
                    detail = desc
                    break
            result['reason'] = f'B2B: {detail}'
            result['confidence'] = 'high' if has_legal_form else 'medium'
            return result

        # IZNIMKA 2: "AGENCIJA ZA ..." + pravna forma (D.O.O.) = privatna agencija
        if 'AGENCIJA ZA' in name and has_legal_form:
            result['buyer_type'] = 'b2b_novat'
            result['is_budget_user'] = False
            result['reason'] = 'B2B: Privatna agencija (d.o.o.) — ne proračunski korisnik'
            result['confidence'] = 'high'
            return result

        # IZNIMKA 3: "URED " + pravna forma = privatni ured
        if 'URED ' in name and has_legal_form:
            result['buyer_type'] = 'b2b_novat'
            result['is_budget_user'] = False
            result['reason'] = 'B2B: Privatni ured (d.o.o./obrt)'
            result['confidence'] = 'high'
            return result

        # Pravi B2G
        result['buyer_type'] = 'b2g'
        result['is_budget_user'] = True
        result['reason'] = f'B2G: ključna riječ "{match_word}" u nazivu'
        result['confidence'] = 'high'
        return result

    # ── 3. UDRUGE / neprofitne ──
    if NONPROFIT_PATTERNS.search(name):
        match_word = NONPROFIT_PATTERNS.search(name).group(0)
        result['is_nonprofit_no_activity'] = True
        result['buyer_type'] = 'udruga_novat'
        result['reason'] = f'Udruga/neprofitna: "{match_word}" u nazivu'
        result['confidence'] = 'medium'
        return result

    # ── 4. B2B — gospodarski subjekti ──
    if has_b2b_match:
        match_word = B2B_PATTERNS.search(name).group(0)
        result['buyer_type'] = 'b2b_novat'
        result['is_budget_user'] = False
        result['reason'] = f'B2B: "{match_word}" u nazivu'
        result['confidence'] = 'high'
        return result

    # ── 5. Fallback — B2C (fizička osoba) ──
    if is_valid_hr_oib(oib):
        result['reason'] = 'B2C: validan OIB, nema B2B/B2G/udruga ključnu riječ'
        result['confidence'] = 'high'
    elif SYNESIS_FAKE_RE.match(oib):
        result['reason'] = 'B2C: Synesis fake OIB, nema ključnu riječ'
        result['confidence'] = 'low'
    else:
        result['reason'] = 'B2C: neprepoznat format OIB-a'
        result['confidence'] = 'low'

    return result


class Command(BaseCommand):
    help = 'Klasificira partnere u buyer_type kategorije (B2C/B2B/B2G/udruga/inozemstvo)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Samo prikaži statistiku bez spremanja',
        )
        parser.add_argument(
            '--company',
            type=int,
            help='Samo partneri jedne firme (company ID)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Ispiši svaki partner koji se mijenja',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        company_id = options.get('company')
        verbose = options['verbose']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n{"═" * 60}\n'
            f'  SMART BUYER TYPE KLASIFIKACIJA\n'
            f'  {"DRY RUN" if dry_run else "PRODUKCIJSKI RUN"}\n'
            f'  {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'{"═" * 60}\n'
        ))

        qs = Partner.objects.all()
        if company_id:
            qs = qs.filter(company_id=company_id)
            self.stdout.write(f'  Filtrirano na company_id={company_id}\n')

        total = qs.count()
        self.stdout.write(f'  Ukupno partnera za analizu: {total}\n')

        stats = {
            'b2c': 0, 'b2b_vat': 0, 'b2b_novat': 0, 'b2g': 0,
            'udruga_vat': 0, 'udruga_novat': 0, 'inozemstvo': 0,
        }
        confidence_stats = {'high': 0, 'medium': 0, 'low': 0, 'skip': 0}
        changed = 0
        skipped = 0
        verification_needed = 0
        changes_log = []

        ctx = transaction.atomic() if not dry_run else nullcontext()
        with ctx:
         for partner in qs.iterator(chunk_size=2000):
            result = classify_partner(partner)
            conf = result['confidence']
            confidence_stats[conf] = confidence_stats.get(conf, 0) + 1

            if conf == 'skip':
                skipped += 1
                continue

            bt = result['buyer_type']
            stats[bt] = stats.get(bt, 0) + 1

            old_bt = partner.buyer_type
            old_budget = partner.is_budget_user
            old_nonprofit = partner.is_nonprofit_no_activity

            new_bt = result['buyer_type']
            new_budget = result['is_budget_user']
            new_nonprofit = result['is_nonprofit_no_activity']

            if old_bt != new_bt or old_budget != new_budget or old_nonprofit != new_nonprofit:
                changed += 1

                if conf in ('medium', 'low'):
                    verification_needed += 1

                if verbose:
                    self.stdout.write(
                        f'  [{conf.upper():6s}] {partner.name[:50]:50s} '
                        f'{old_bt:12s} -> {new_bt:12s}  | {result["reason"]}'
                    )

                changes_log.append({
                    'id': partner.id,
                    'name': partner.name,
                    'old': old_bt,
                    'new': new_bt,
                    'confidence': conf,
                    'reason': result['reason'],
                    'is_budget_user': new_budget,
                    'is_nonprofit_no_activity': new_nonprofit,
                })

                if not dry_run:
                    update_fields = ['buyer_type', 'is_budget_user',
                                     'is_nonprofit_no_activity', 'updated_at']
                    partner.buyer_type = new_bt
                    partner.is_budget_user = new_budget
                    partner.is_nonprofit_no_activity = new_nonprofit

                    if conf in ('medium', 'low'):
                        marker = f'\n[AUTO-CLASSIFY {timezone.now():%Y-%m-%d}] needs_verification=True | {result["reason"]}'
                        if 'needs_verification' not in (partner.notes or ''):
                            partner.notes = (partner.notes or '') + marker
                            update_fields.append('notes')

                    partner.save(update_fields=update_fields)

        # ═══════════════════════════════════════════════════════
        # STATISTIKA
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n{"─" * 60}\n  REZULTATI\n{"─" * 60}'
        ))

        self.stdout.write(f'\n  DISTRIBUCIJA BUYER TYPE:')
        for bt, cnt in sorted(stats.items(), key=lambda x: -x[1]):
            pct = (cnt / total * 100) if total else 0
            bar = '█' * int(pct / 2)
            self.stdout.write(f'    {bt:15s} {cnt:>6d}  ({pct:5.1f}%)  {bar}')

        self.stdout.write(f'\n  POUZDANOST:')
        for level, cnt in sorted(confidence_stats.items(), key=lambda x: -x[1]):
            self.stdout.write(f'    {level:10s} {cnt:>6d}')

        self.stdout.write(f'\n  SAŽETAK:')
        self.stdout.write(f'    Ukupno analizirano:      {total:>6d}')
        self.stdout.write(f'    Promijenjeno:            {changed:>6d}')
        self.stdout.write(f'    Preskočeno (tehničko):   {skipped:>6d}')
        self.stdout.write(f'    Treba verifikaciju:      {verification_needed:>6d}')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n  DRY RUN — ništa nije spremljeno u bazu!\n'
                f'  Pokreni bez --dry-run za produkcijski run.\n'
            ))

            self.stdout.write(f'\n  UZORAK PROMJENA (max 5 po tipu):')
            shown_types = {}
            for ch in changes_log:
                bt = ch['new']
                if bt not in shown_types:
                    shown_types[bt] = 0
                if shown_types[bt] < 5:
                    self.stdout.write(
                        f'    [{ch["confidence"]:6s}] {ch["name"][:45]:45s} -> {bt:15s} | {ch["reason"][:60]}'
                    )
                    shown_types[bt] += 1
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n  SPREMLJENO! {changed} partnera ažurirano.\n'
            ))
