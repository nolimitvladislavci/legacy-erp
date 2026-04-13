"""
RAG AI Chat — Knowledge Base model + seed data + retrieval u system prompt
"""
import os
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# 1. KNOWLEDGE BASE MODEL
# ══════════════════════════════════════════════════════════════════════

models_path = os.path.join(BASE, 'ai_assistant/models.py')
with open(models_path) as f:
    mc = f.read()

if 'KnowledgeArticle' not in mc:
    kb_model = '''

class KnowledgeArticle(models.Model):
    """
    RAG Knowledge Base — strukturirani članci koje AI koristi za odgovore.
    Umjesto haluciniranja, AI povlači točne podatke iz ove baze.
    """
    MODULE_CHOICES = [
        ('pos', 'POS (Blagajna)'),
        ('invoicing', 'Fakturiranje'),
        ('inventory', 'Skladište'),
        ('experiences', 'Iskustva / Agro-Turizam'),
        ('work_orders', 'Radni nalozi'),
        ('rental', 'Smještaj / Rental'),
        ('udruge', 'Udruge'),
        ('marketplace', 'OPG Tržnica'),
        ('compliance', 'Zakoni / Compliance'),
        ('borg', 'BORG operacije'),
        ('general', 'Opće'),
    ]

    module = models.CharField(max_length=30, choices=MODULE_CHOICES, db_index=True)
    title = models.CharField(max_length=200, verbose_name='Naslov')
    content = models.TextField(verbose_name='Sadržaj',
                                help_text='Markdown format. AI koristi ovo za RAG odgovore.')
    keywords = models.CharField(max_length=500, blank=True,
                                 help_text='Ključne riječi za pretragu, odvojene zarezom')
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=5,
                                            help_text='1=najvažnije, 10=najmanje')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Članak baze znanja'
        verbose_name_plural = 'Članci baze znanja'
        ordering = ['module', 'priority', 'title']

    def __str__(self):
        return f'[{self.module}] {self.title}'
'''
    mc += kb_model
    with open(models_path, 'w') as f:
        f.write(mc)
    print("[OK] ai_assistant/models.py — KnowledgeArticle model dodan")


# ══════════════════════════════════════════════════════════════════════
# 2. ADMIN
# ══════════════════════════════════════════════════════════════════════

admin_path = os.path.join(BASE, 'ai_assistant/admin.py')
with open(admin_path) as f:
    ac = f.read()

if 'KnowledgeArticle' not in ac:
    ac += '''
from .models import KnowledgeArticle

@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('module', 'title', 'priority', 'is_active', 'updated_at')
    list_filter = ('module', 'is_active')
    search_fields = ('title', 'content', 'keywords')
    list_editable = ('priority', 'is_active')
'''
    with open(admin_path, 'w') as f:
        f.write(ac)
    print("[OK] ai_assistant/admin.py — KnowledgeArticle admin")


# ══════════════════════════════════════════════════════════════════════
# 3. RAG RETRIEVAL — inject u system prompt
# ══════════════════════════════════════════════════════════════════════

client_path = os.path.join(BASE, 'ai_assistant/claude_client.py')
with open(client_path) as f:
    cc = f.read()

if 'retrieve_knowledge' not in cc:
    # Dodaj retrieval funkciju
    rag_code = '''

def retrieve_knowledge(module_context='', query='', limit=5):
    """
    RAG retrieval — dohvati relevantne članke iz KnowledgeArticle.
    Koristi keyword matching + module filter.
    """
    from .models import KnowledgeArticle
    from django.db.models import Q

    qs = KnowledgeArticle.objects.filter(is_active=True)

    # Module filter iz page context-a
    module_map = {
        'experiences': 'experiences',
        'pos': 'pos',
        'inventory': 'inventory',
        'invoicing': 'invoicing',
        'borg': 'borg',
        'udruge': 'udruge',
        'marketplace': 'marketplace',
        'work-orders': 'work_orders',
        'recall': 'experiences',
        'rental': 'rental',
    }
    detected_module = None
    for keyword, module in module_map.items():
        if keyword in module_context.lower():
            detected_module = module
            break

    if detected_module:
        # Prioritet: modul-specifični + general
        qs = qs.filter(Q(module=detected_module) | Q(module='general') | Q(module='compliance'))
    
    # Keyword search iz query-ja
    if query:
        words = query.lower().split()[:5]  # Max 5 riječi
        q_filter = Q()
        for word in words:
            if len(word) > 2:  # Ignoriraj kratke riječi
                q_filter |= Q(keywords__icontains=word) | Q(title__icontains=word) | Q(content__icontains=word)
        if q_filter:
            qs = qs.filter(q_filter)

    articles = qs.order_by('priority')[:limit]
    
    if not articles:
        return ''

    kb_text = "\\n\\n## Baza znanja (RAG) — koristi ove podatke za točan odgovor:\\n"
    for art in articles:
        kb_text += f"\\n### {art.title}\\n{art.content}\\n"
    
    return kb_text
'''
    cc += rag_code
    
    # Inject retrieve_knowledge u _build_contextual_system_prompt
    old_return = "    return SYSTEM_PROMPT + ctx"
    new_return = """    # RAG: dohvati relevantne članke iz baze znanja
    try:
        kb = retrieve_knowledge(
            module_context=getattr(company, 'business_type', ''),
            query='',  # Query se dodaje u chat_api
        )
        ctx += kb
    except (AttributeError, TypeError):
        pass

    return SYSTEM_PROMPT + ctx"""
    
    cc = cc.replace(old_return, new_return)
    
    with open(client_path, 'w') as f:
        f.write(cc)
    print("[OK] ai_assistant/claude_client.py — RAG retrieval u system prompt")


# ══════════════════════════════════════════════════════════════════════
# 4. CHAT API — proslijedi module_context i query u RAG
# ══════════════════════════════════════════════════════════════════════

views_path = os.path.join(BASE, 'ai_assistant/views.py')
with open(views_path) as f:
    vc = f.read()

if 'retrieve_knowledge' not in vc:
    # Inject RAG u chat_api — dodaj knowledge u system prompt per-query
    old_system = '            system=_build_contextual_system_prompt(request.user, company),'
    new_system = '''            system=_build_contextual_system_prompt(request.user, company) + _get_rag_context(module_context, user_message),'''
    
    vc = vc.replace(old_system, new_system)
    
    # Dodaj helper funkciju
    if '_get_rag_context' not in vc:
        rag_helper = '''
def _get_rag_context(module_context, query):
    """Dohvati RAG kontekst za chat."""
    try:
        from .claude_client import retrieve_knowledge
        return retrieve_knowledge(module_context=module_context, query=query, limit=3)
    except ImportError:
        return ''

'''
        # Inject prije _chat_api_inner
        vc = vc.replace('def _chat_api_inner(request):', rag_helper + 'def _chat_api_inner(request):')
    
    with open(views_path, 'w') as f:
        f.write(vc)
    print("[OK] ai_assistant/views.py — RAG context per-query")


# ══════════════════════════════════════════════════════════════════════
# 5. SEED DATA — početni članci za knowledge base
# ══════════════════════════════════════════════════════════════════════

seed_path = os.path.join(BASE, 'ai_assistant/management/commands')
os.makedirs(seed_path, exist_ok=True)
init_path = os.path.join(BASE, 'ai_assistant/management/__init__.py')
if not os.path.exists(init_path):
    with open(init_path, 'w') as f: f.write('')
init_path2 = os.path.join(seed_path, '__init__.py')
if not os.path.exists(init_path2):
    with open(init_path2, 'w') as f: f.write('')

seed_cmd = '''"""Seed KnowledgeArticle s inicijalnim compliance/help artiklima."""
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
            f'\\nDone: {created} created, {len(ARTICLES) - created} updated'
        ))
'''

with open(os.path.join(seed_path, 'seed_knowledge.py'), 'w') as f:
    f.write(seed_cmd)
print("[OK] ai_assistant/management/commands/seed_knowledge.py — 9 seed članaka")


print("\n═══════════════════════════════════════════")
print("RAG AI KOMPLETIRAN")
print("  1. KnowledgeArticle model")
print("  2. Admin registracija")
print("  3. retrieve_knowledge() RAG retrieval")
print("  4. System prompt injection per-query")
print("  5. 9 seed članaka (compliance + module help)")
print("═══════════════════════════════════════════")
