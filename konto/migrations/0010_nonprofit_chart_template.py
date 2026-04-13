"""
Neprofitni kontni plan (HR) prema Pravilniku o neprofitnom racunovodstvu.
Klase: 0=Imovina, 1=Obveze+Vlastiti izvori, 2=Rashodi (rebalans),
       3=Prihodi, 4=Rashodi, 5=Vlastiti izvori (rebalans)
       9=Izvanbilancni
"""

from django.db import migrations


NONPROFIT_ACCOUNTS = [
    # Klasa 0 — Nefinancijska imovina
    ("0", "Nefinancijska imovina", "asset"),
    ("01", "Neproizvedena dugotrajna imovina", "asset"),
    ("02", "Proizvedena dugotrajna imovina", "asset"),
    ("03", "Plemeniti metali i ostale pohranjene vrijednosti", "asset"),
    ("04", "Sitni inventar", "asset"),
    ("05", "Dugotrajna nefinancijska imovina u pripremi", "asset"),
    ("06", "Proizvedena kratkotrajna imovina", "asset"),
    # Klasa 1 — Financijska imovina
    ("1", "Financijska imovina", "asset"),
    ("11", "Novac u banci i blagajni", "asset"),
    ("12", "Depoziti i jamcevni polozi", "asset"),
    ("13", "Potraživanja za prihode", "asset"),
    ("16", "Potraživanja za više plaćene poreze", "asset"),
    ("19", "Rashodi buducih razdoblja i nedospjela naplata", "asset"),
    # Klasa 2 — Obveze
    ("2", "Obveze", "liability"),
    ("21", "Obveze za rashode", "liability"),
    ("23", "Obveze za kredite i zajmove", "liability"),
    ("24", "Odgodeno placanje rashoda i prihodi buducih razdoblja", "liability"),
    ("25", "Obveze za PDV i ostale poreze", "liability"),
    # Klasa 3 — Prihodi (KLJUCNA RAZLIKA od poduzetnickog!)
    ("3", "Prihodi", "income"),
    ("31", "Prihodi od prodaje roba i pruzanja usluga", "income"),
    ("32", "Prihodi od clanarina i clanskih doprinosa", "income"),
    ("33", "Prihodi po posebnim propisima", "income"),
    ("34", "Prihodi od imovine", "income"),
    ("35", "Prihodi od donacija", "income"),
    ("36", "Ostali prihodi", "income"),
    ("37", "Prihodi od povezanih neprofitnih org.", "income"),
    ("38", "Namjenski prihodi (projekti, grantovi)", "income"),
    # Klasa 4 — Rashodi
    ("4", "Rashodi", "expense"),
    ("41", "Rashodi za radnike", "expense"),
    ("42", "Materijalni rashodi", "expense"),
    ("43", "Rashodi amortizacije", "expense"),
    ("44", "Financijski rashodi", "expense"),
    ("45", "Donacije", "expense"),
    ("46", "Ostali rashodi", "expense"),
    # Klasa 5 — Vlastiti izvori (kapital)
    ("5", "Vlastiti izvori", "equity"),
    ("51", "Vlastiti izvori", "equity"),
    ("52", "Visak/manjak prihoda", "equity"),
    # Klasa 9 — Izvanbilancni
    ("9", "Izvanbilancni zapisi", "asset"),
]


def create_nonprofit_template(apps, schema_editor):
    """Kreira neprofitni kontni plan kao template za udruge."""
    from django.db import connection

    # Check if nonprofit template marker exists in any company
    # This is a data migration — only creates template accounts for
    # companies with business_type in ('udruga', 'zadruga', 'ustanova')
    # that don't yet have konto accounts
    Company = apps.get_model("companies", "Company")
    KontoAccount = apps.get_model("konto", "KontoAccount")

    nonprofit_companies = Company.objects.filter(business_type__in=["udruga", "zadruga", "ustanova"])
    for company in nonprofit_companies:
        if KontoAccount.objects.filter(company=company).exists():
            continue  # already has accounts
        for code, name, acc_type in NONPROFIT_ACCOUNTS:
            KontoAccount.objects.create(
                company=company,
                code=code,
                name=name,
                account_type=acc_type,
                is_active=True,
            )


def reverse(apps, schema_editor):
    pass  # Don't delete accounts on reverse


class Migration(migrations.Migration):
    dependencies = [
        ("konto", "0009_alter_journalentry_source_type"),
        ("companies", "0025_add_opg_udruga_business_types"),
    ]

    operations = [
        migrations.RunPython(create_nonprofit_template, reverse),
    ]
