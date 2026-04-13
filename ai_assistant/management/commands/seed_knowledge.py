"""Seed KnowledgeArticle s inicijalnim compliance/help artiklima."""
from django.core.management.base import BaseCommand


ARTICLES = [
    # ── COMPLIANCE ──
    {
        "module": "compliance",
        "title": "Karenca lijekova za životinje — Zakon o higijeni hrane",
        "keywords": "karenca, antibiotik, lijek, jaja, mlijeko, meso, PHI, zabrana prodaje, veterinar",
        "priority": 1,
        "content": """Karenca (Pre-Harvest Interval) je razdoblje nakon primjene lijeka tijekom kojeg se proizvodi životinjskog podrijetla NE SMIJU stavljati u promet.

**Zakonska podloga:** Uredba (EU) 2019/6, Zakon o veterinarskim lijekovima (NN 84/19), Zakon o higijeni hrane (NN 81/13).

**Kako BORG to implementira:**
- FlockHealthRecord.karenca_dana — broj dana zabrane
- POS Hard Block — automatski blokira prodaju artikala s source_flock pod karencom
- LOT-level preciznost — blokira samo LOT iz tretiranog jata, ne sve proizvode
- MarketplaceBridge — auto-pull s tržnice

**Kazne:** Zatvaranje objekta, do 200.000 HRK (čl. 91 Zakona o hrani).""",
    },
    {
        "module": "compliance",
        "title": "Avansni račun i storno — čl. 79 ZPDV",
        "keywords": "avans, predujam, depozit, storno, PDV, račun, no-show, povrat",
        "priority": 1,
        "content": """Kad se primi avansna uplata (depozit), MORA se izdati Avansni račun (doctype='A') — čl. 79 st. 1 ZPDV.

**No-show flow:**
1. Gost uplati depozit → Avansni račun (fiskaliziran)
2. Gost se ne pojavi → Storno avansnog računa (poništava PDV)
3. Izdaje se Konačni račun za "Naknadu za nedolazak" (doctype='R')

**NIKAD ne smije biti:** samo novi račun bez storna predujma — to je dvostruko oporezivanje.

**Kazne:** Porezna uprava, čl. 115 ZPDV — do 500.000 HRK.""",
    },
    {
        "module": "compliance",
        "title": "SplitAllocation — interna upotreba vs. prodaja",
        "keywords": "split, alokacija, repromaterijal, interna upotreba, izdatnica, zaliha",
        "priority": 2,
        "content": """Kad OPG prebacuje robu iz "za prodaju" u "internu upotrebu" (npr. jaja za pripremu doručka), MORA generirati internu izdatnicu (StockMovement type='internal_use').

**Zašto:** Porezna inspekcija uspoređuje ulaz i izlaz robe. Ako 100 jaja uđe a samo 80 se proda, fali 20 — bez izdatnice to izgleda kao utaja.

**BORG implementacija:**
- inventory/services/split_allocation.py: allocate_to_inhouse()
- Automatski StockMovement s tipom 'internal_use'
- reserved_inhouse polje na InventoryItem"""
    },
    # ── EXPERIENCES ──
    {
        "module": "experiences",
        "title": "BOM Normativi — kako funkcionira alokacija zaliha",
        "keywords": "BOM, normativ, degustacija, sir, vino, količina, alokacija, check-in",
        "priority": 2,
        "content": """ExperienceInclusion = Bill of Materials (BOM) za svako iskustvo.

**Primjer:** Degustacija sira i vina, 10 gostiju:
- Sir Paški: 0.05 kg/os × 10 = 0.50 kg
- Malvazija: 0.20 L/os × 10 = 2.00 L
- Kruh: 0.10 kg/os × 10 = 1.00 kg

**Flow:** Booking → Check-in → allocate_to_inhouse() za svaki BOM item × pax_count
**API:** GET /experiences/<pk>/normativ/?pax=10 — JSON preview s stock statusom"""
    },
    {
        "module": "experiences",
        "title": "Booking lifecycle",
        "keywords": "rezervacija, booking, depozit, check-in, no-show, otkazivanje",
        "priority": 2,
        "content": """Status flow: pending → confirmed → checked_in → completed
                                                    → no_show (depozit zadržan + storno + konačni račun)
                                                    → cancelled (puni povrat ako >12h prije)

**Depozit:** Automatski = price_per_person × pax × deposit_pct / 100
**Check-in:** Auto-alocira inventory (BOM × pax) kroz SplitAllocation
**No-show:** Celery task u 22:00 — storno predujma + konačni račun"""
    },
    # ── POS ──
    {
        "module": "pos",
        "title": "Z-izvještaj i zatvaranje smjene",
        "keywords": "Z, izvještaj, smjena, zatvaranje, gotovina, prebrojavanje",
        "priority": 3,
        "content": """Z gumb zatvara smjenu. Flow:
1. Klik Z → modal za prebrojavanje gotovine
2. Unos fizičke gotovine → sustav uspoređuje s evidentiranom
3. Razlika = manjak ili višak → automatski se evidentira
4. Z-izvještaj generiran (PDF) — arhivira se 11 godina (Zakon o fiskalizaciji)"""
    },
    # ── INVENTORY ──
    {
        "module": "inventory",
        "title": "LOT slijedivost — EU 178/2002",
        "keywords": "LOT, šarža, batch, slijedivost, FEFO, rok trajanja",
        "priority": 2,
        "content": """Svaki StockBatch ima: batch_number, expiry_date, source_flock (za perad).

**FEFO:** First Expired First Out — šarže se sortiraju po roku trajanja.
**Karenca link:** StockBatch.source_flock → Flock → has_active_karenca
**POS check:** Ako LOT dolazi iz jata pod karencom → HARD BLOCK na prodaju"""
    },
    # ── BORG ──
    {
        "module": "borg",
        "title": "BORG Hub — operativni centar",
        "keywords": "hub, dashboard, operacije, SLA, intervencije, nalozi",
        "priority": 3,
        "content": """BORG Hub (/dashboard/operations/) agregira:
- SLA kršenja (real-time)
- Hitne intervencije (top 5)
- Radni nalozi (kanban)
- Burza upiti
- Experiences danas (gosti, no-shows, prihod)
- Inventory alerte (niska zaliha, karenca, istekle šarže)
- Financijski pulse (današnji promet, neplaćeno)

**Auto-refresh:** HTMX svake 60s. Redis cache 45s TTL."""
    },
    # ── GENERAL ──
    {
        "module": "general",
        "title": "Kako LIMIT Connect ERP radi — pregled modula",
        "keywords": "modul, pregled, ERP, sustav, pomoć",
        "priority": 5,
        "content": """LIMIT Connect = ERP za male poduzetnike (HR/DE).

**Moduli:** POS (blagajna), Fakturiranje, Skladište, Experiences (agro-turizam), Radni nalozi, Rental (smještaj), Udruge (članstvo, donacije, perad), Marketplace (OPG tržnica), Konto (knjigovodstvo), Tax Wizard, eRačun, Payroll.

**AI:** Chat asistent (Claude Haiku), Signal Triage, Patrol (anomaly detection), Smart Dispatch.
**Sigurnost:** CSRF zaštita, karenca enforcement, Schema Drift sentinel."""
    },
]


class Command(BaseCommand):
    help = 'Seed KnowledgeArticle bazu s inicijalnim člancima'

    def handle(self, *args, **options):
        from ai_assistant.models import KnowledgeArticle
        created = 0
        for art in ARTICLES:
            obj, was_created = KnowledgeArticle.objects.update_or_create(
                module=art['module'],
                title=art['title'],
                defaults={
                    'content': art['content'],
                    'keywords': art.get('keywords', ''),
                    'priority': art.get('priority', 5),
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f'  + {obj}')
            else:
                self.stdout.write(f'  ~ {obj} (updated)')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {created} created, {len(ARTICLES) - created} updated'
        ))
