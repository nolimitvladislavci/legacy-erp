"""
tax_wizard/seed.py — Inicijalni podaci za Porezni Savjetnik.
Pokreni: python manage.py shell < tax_wizard/seed.py
"""
import os
import sys
import django

# Setup
sys.path.insert(0, '/var/www/fina-connect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datetime import date
from decimal import Decimal
from tax_wizard.models import (
    TaxFormTemplate,
    PausalTier,
    OsobniOdbitakKoeficijent,
)


# ═══════════════════════════════════════════════════════════════
#  PO-SD TEMPLATE — JSON Wizard Schema (2026)
# ═══════════════════════════════════════════════════════════════

posd_schema = {
    "steps": [
        {
            "id": "intro",
            "title": "Osnovni podaci",
            "title_en": "Basic information",
            "fields": [
                {
                    "name": "oib",
                    "type": "oib",
                    "label": "OIB obveznika",
                    "label_en": "Taxpayer OIB",
                    "required": True,
                    "help_text": "Osobni identifikacijski broj paušalnog obrtnika",
                    "help_text_en": "Personal identification number of the lump-sum sole proprietor",
                    "ai_hint": "Auto-fill iz company.oib ako je korisnik naš komitent",
                    "source": "companies.Company.oib"
                },
                {
                    "name": "ime_prezime",
                    "type": "text",
                    "label": "Ime i prezime",
                    "label_en": "Full name",
                    "required": True,
                    "source": "auth.User.get_full_name"
                },
                {
                    "name": "adresa",
                    "type": "text",
                    "label": "Adresa prebivališta",
                    "label_en": "Residential address",
                    "required": True,
                    "ai_hint": "Provjeri potpomognuto područje za viši osobni odbitak",
                    "source": "companies.Company.address"
                },
                {
                    "name": "naziv_obrta",
                    "type": "text",
                    "label": "Naziv obrta",
                    "label_en": "Business name",
                    "required": True,
                    "source": "companies.Company.name"
                },
                {
                    "name": "djelatnost_nkd",
                    "type": "text",
                    "label": "Djelatnost (NKD šifra)",
                    "label_en": "Business activity (NKD code)",
                    "required": True,
                    "help_text": "Glavna djelatnost prema Nacionalnoj klasifikaciji djelatnosti"
                },
                {
                    "name": "porezna_godina",
                    "type": "integer",
                    "label": "Porezna godina",
                    "label_en": "Tax year",
                    "required": True,
                    "default": 2025,
                    "min": 2020,
                    "max": 2026
                }
            ],
            "ai_message": "Povlačim vaše podatke iz sustava — provjerite i ispravite ako je potrebno.",
            "ai_message_en": "Pulling your data from the system — please verify and correct if needed."
        },
        {
            "id": "primitci",
            "title": "Primitci po kvartalima",
            "title_en": "Quarterly income",
            "fields": [
                {
                    "name": "q1_primitak",
                    "type": "decimal",
                    "label": "I. kvartal (siječanj–ožujak)",
                    "label_en": "Q1 (January–March)",
                    "required": True,
                    "default": 0,
                    "min": 0,
                    "max": 60000,
                    "help_text": "Ukupni primitci za I. kvartal (EUR)",
                    "ai_hint": "Auto-fill iz invoicing.Invoice WHERE quarter=1",
                    "source": "invoicing.Invoice",
                    "source_filter": {"quarter": 1}
                },
                {
                    "name": "q2_primitak",
                    "type": "decimal",
                    "label": "II. kvartal (travanj–lipanj)",
                    "label_en": "Q2 (April–June)",
                    "required": True,
                    "default": 0,
                    "min": 0,
                    "max": 60000,
                    "source": "invoicing.Invoice",
                    "source_filter": {"quarter": 2}
                },
                {
                    "name": "q3_primitak",
                    "type": "decimal",
                    "label": "III. kvartal (srpanj–rujan)",
                    "label_en": "Q3 (July–September)",
                    "required": True,
                    "default": 0,
                    "min": 0,
                    "max": 60000,
                    "source": "invoicing.Invoice",
                    "source_filter": {"quarter": 3}
                },
                {
                    "name": "q4_primitak",
                    "type": "decimal",
                    "label": "IV. kvartal (listopad–prosinac)",
                    "label_en": "Q4 (October–December)",
                    "required": True,
                    "default": 0,
                    "min": 0,
                    "max": 60000,
                    "source": "invoicing.Invoice",
                    "source_filter": {"quarter": 4}
                }
            ],
            "ai_message": "Zbrajam primitke i određujem vaš porezni razred...",
            "ai_message_en": "Calculating total income and determining your tax tier...",
            "validation_rules": [
                {
                    "rule": "sum_lte_60000",
                    "fields": ["q1_primitak", "q2_primitak", "q3_primitak", "q4_primitak"],
                    "message": "⚠️ Ukupni primitci prelaze 60.000 EUR — MORATE prijeći na redovni obrt i voditi poslovne knjige! Kontaktirajte svog računovođu.",
                    "message_en": "⚠️ Total income exceeds EUR 60,000 — you MUST switch to regular bookkeeping! Contact your accountant.",
                    "severity": "error"
                },
                {
                    "rule": "sum_gte_0",
                    "fields": ["q1_primitak", "q2_primitak", "q3_primitak", "q4_primitak"],
                    "message": "Primitci ne mogu biti negativni.",
                    "severity": "error"
                }
            ]
        },
        {
            "id": "izracun",
            "title": "Izračun poreza",
            "title_en": "Tax calculation",
            "fields": [
                {
                    "name": "ukupni_primitak",
                    "type": "decimal",
                    "label": "Ukupni godišnji primitak",
                    "label_en": "Total annual income",
                    "computed": True,
                    "formula": "q1_primitak + q2_primitak + q3_primitak + q4_primitak",
                    "readonly": True
                },
                {
                    "name": "porezni_razred",
                    "type": "integer",
                    "label": "Porezni razred (tier)",
                    "label_en": "Tax tier",
                    "computed": True,
                    "formula": "tier_from_income(ukupni_primitak)",
                    "readonly": True
                },
                {
                    "name": "godisnji_porez",
                    "type": "decimal",
                    "label": "Godišnji porez (EUR)",
                    "label_en": "Annual tax (EUR)",
                    "computed": True,
                    "formula": "tax_from_tier(porezni_razred)",
                    "readonly": True
                },
                {
                    "name": "vec_placeni_porez",
                    "type": "decimal",
                    "label": "Već plaćeni predujam poreza (EUR)",
                    "label_en": "Tax already paid in advance (EUR)",
                    "required": True,
                    "default": 0,
                    "min": 0,
                    "help_text": "Koliko ste ukupno platili kvartalnih predujmova poreza u ovoj godini?",
                    "help_text_en": "How much quarterly advance tax did you pay this year?"
                },
                {
                    "name": "razlika",
                    "type": "decimal",
                    "label": "Razlika za uplatu/povrat (EUR)",
                    "label_en": "Difference to pay/refund (EUR)",
                    "computed": True,
                    "formula": "godisnji_porez - vec_placeni_porez",
                    "readonly": True
                }
            ],
            "ai_message": "Izračun je gotov. Provjerite razliku — ako je negativna, imate pravo na povrat!",
            "ai_message_en": "Calculation complete. Check the difference — if negative, you're entitled to a refund!"
        },
        {
            "id": "ai_savjeti",
            "title": "Provjera i savjeti",
            "title_en": "Review and tips",
            "fields": [
                {
                    "name": "blizu_granice",
                    "type": "boolean",
                    "label": "Primitci su blizu granice razreda?",
                    "computed": True,
                    "readonly": True,
                    "ai_hint": "Ako je korisnik unutar 500€ od granice razreda, predloži optimizaciju fakturiranja"
                },
                {
                    "name": "blizu_60k",
                    "type": "boolean",
                    "label": "Primitci su blizu 60.000 EUR limita?",
                    "computed": True,
                    "readonly": True,
                    "ai_hint": "Ako je korisnik iznad 50.000€, upozori na limit i predloži d.o.o. simulaciju"
                }
            ],
            "ai_message": "Analiziram vaše podatke za potencijalne uštede...",
            "ai_message_en": "Analyzing your data for potential savings...",
            "ai_checks": [
                {
                    "check": "tier_boundary_proximity",
                    "message_template": "Vaši primitci ({total}€) su {diff}€ {direction} granice razreda {tier}. {tip}",
                    "tip_below": "Simulacija pokazuje da bi razred {lower_tier} rezultirao s {savings}€ manjim porezom godišnje.",
                    "tip_above": "Primitci su u razredu {tier} — sljedeći razred počinje na {next_boundary}€."
                },
                {
                    "check": "vat_threshold_proximity",
                    "threshold": 60000,
                    "warning_at": 50000,
                    "message": "Primitci su {total}€ — do PDV limita (60.000€) preostaje {remaining}€. Ako očekujete rast, razmislite o prijelazu na d.o.o."
                },
                {
                    "check": "potpomognuto_podrucje",
                    "message": "Vaša adresa ({address}) je na potpomognutom području — imate pravo na povećani osobni odbitak ({amount}€/mj umjesto 600€)."
                }
            ]
        },
        {
            "id": "preview",
            "title": "Pregled i podnošenje",
            "title_en": "Preview and submit",
            "fields": [],
            "is_preview": True,
            "ai_message": "Sve izgleda u redu! Možete preuzeti PO-SD obrazac u XML formatu za upload na ePorezna, ili PDF za vlastitu arhivu.",
            "ai_message_en": "Everything looks good! You can download the PO-SD form as XML for upload to ePorezna, or PDF for your records.",
            "actions": ["download_xml", "download_pdf", "send_to_accountant"]
        }
    ],
    "output_xml_template": "posd_2026_v1",
    "legal_references": [
        "Zakon o porezu na dohodak (NN 115/16, 106/18, 121/19, 32/20, 138/20, 151/22, 114/23, 35/25) — čl. 82.",
        "Pravilnik o paušalnom oporezivanju samostalne djelatnosti (NN 1/20, 1/21, 156/22, 143/23) — čl. 2.–8.",
        "Zakon o doprinosima (NN 84/08, ... , 35/25) — čl. 82.a"
    ]
}


posd_template, created = TaxFormTemplate.objects.update_or_create(
    form_type='PO-SD',
    version='2026-v1',
    defaults={
        'name': 'PO-SD — Izvješće o paušalnom dohotku od samostalne djelatnosti',
        'name_en': 'PO-SD — Lump-sum self-employment income report',
        'schema': posd_schema,
        'applicable_business_types': ['obrt'],
        'applicable_countries': ['HR'],
        'filing_deadline_rule': 'jan-15',
        'xml_template_name': 'posd_2026_v1',
        'is_active': True,
        'valid_from': date(2026, 1, 1),
        'valid_until': date(2026, 12, 31),
        'ai_system_prompt': (
            'Ti si porezni kalkulator za paušalne obrtnike u Hrvatskoj. '
            'Prikazuješ simulacije i izračune na temelju unesenih podataka '
            'i trenutno važećih poreznih stopa za 2026. godinu. '
            'NIKADA ne koristi riječi: preporučujem, savjetujem, trebali biste. '
            'UVIJEK koristi: simulacija pokazuje, izračun rezultira, prema važećim stopama. '
            'Paušalni obrtnici plaćaju fiksni porez prema razredima (tierovima) '
            'te fiksne mjesečne doprinose (MIO + zdravstveno). '
            'Limit za paušalni obrt je 60.000 EUR godišnje — iznad toga prelaze na redovne knjige. '
            'Na kraju svake poruke dodaj: "Ovo je informativni izračun, ne pravni savjet."'
        ),
    }
)
status = 'CREATED' if created else 'UPDATED'
print(f'[{status}] TaxFormTemplate: {posd_template}')


# ═══════════════════════════════════════════════════════════════
#  PAUŠAL TIER TABLICA 2026
# ═══════════════════════════════════════════════════════════════

tiers_2026 = [
    (1, 0, 12500, 1530, 127.50, 290.98),
    (2, 12501, 17500, 2142, 178.50, 290.98),
    (3, 17501, 25000, 3060, 255.00, 290.98),
    (4, 25001, 40000, 4896, 408.00, 290.98),
    (5, 40001, 60000, 7344, 612.00, 290.98),
]

for tier_num, min_inc, max_inc, annual, monthly, contrib in tiers_2026:
    obj, created = PausalTier.objects.update_or_create(
        valid_year=2026,
        tier_number=tier_num,
        defaults={
            'min_income': Decimal(str(min_inc)),
            'max_income': Decimal(str(max_inc)),
            'annual_tax': Decimal(str(annual)),
            'monthly_tax': Decimal(str(monthly)),
            'monthly_contributions': Decimal(str(contrib)),
            'is_active': True,
        }
    )
    status = 'CREATED' if created else 'UPDATED'
    print(f'[{status}] PausalTier: {obj}')


# ═══════════════════════════════════════════════════════════════
#  OSOBNI ODBITAK KOEFICIJENTI 2026
# ═══════════════════════════════════════════════════════════════

koeficijenti_2026 = [
    ('dependent',     Decimal('0.5'),  'Provjeri bračni status i uzdržavane članove obitelji'),
    ('child_1',       Decimal('0.5'),  'Provjeri ima li korisnik djecu u sustavu'),
    ('child_2',       Decimal('0.7'),  'Drugo dijete — viši koeficijent'),
    ('child_3',       Decimal('1.0'),  'Treće dijete'),
    ('child_4',       Decimal('1.4'),  'Četvrto dijete'),
    ('child_5_plus',  Decimal('1.9'),  'Peto i svako daljnje dijete — eksponencijalni rast koeficijenta'),
    ('partial_dis',   Decimal('0.3'),  'Pitaj korisnika ima li potvrdu o djelomičnoj invalidnosti'),
    ('full_dis',      Decimal('1.0'),  'Potvrda o 100% invalidnosti'),
    ('hrvi_1',        Decimal('1.5'),  'HRVI I. skupina — potrebna potvrda MO'),
    ('hrvi_2',        Decimal('1.0'),  'HRVI II. skupina'),
    ('hrvi_other',    Decimal('0.5'),  'HRVI ostale skupine'),
]

base = Decimal('600')
for category, coeff, hint in koeficijenti_2026:
    obj, created = OsobniOdbitakKoeficijent.objects.update_or_create(
        valid_year=2026,
        category=category,
        defaults={
            'coefficient': coeff,
            'base_amount': base,
            'monthly_amount': (base * coeff).quantize(Decimal('0.01')),
            'detection_hint': hint,
            'is_active': True,
        }
    )
    status = 'CREATED' if created else 'UPDATED'
    print(f'[{status}] OsobniOdbitak: {obj}')


print('\n✅ Seed complete! PO-SD template + 5 tierova + 11 koeficijenata')
