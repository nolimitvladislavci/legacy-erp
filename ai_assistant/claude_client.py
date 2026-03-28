import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
# Pricing: $0.80/MTok input, $4.00/MTok output (claude-haiku-4-5-20251001, 2025)
COST_INPUT_PER_TOKEN  = 0.80 / 1_000_000   # USD
COST_OUTPUT_PER_TOKEN = 4.0  / 1_000_000   # USD


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a Claude API call."""
    return input_tokens * COST_INPUT_PER_TOKEN + output_tokens * COST_OUTPUT_PER_TOKEN


def get_claude_client():
    """Return an Anthropic client using the API key from environment."""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured — set it in .env")
    return anthropic.Anthropic(api_key=api_key)


SYSTEM_PROMPT = """Ti si Connect — osobni digitalni savjetnik za poslovne korisnike LIMIT Connect ERP sustava.

## Tko si ti
Nisi generički chatbot. Ti si iskusan poslovni savjetnik koji poznaje svaku firmu, svaki dokument i svaki proces u sustavu. Uvijek vidiš širu sliku — ne samo što se dogodilo, nego što to znači i što treba poduzeti.

## Kako komuniciraš
- Govoriš kao pouzdani savjetnik, ne kao sustav koji javlja status
- Nikad suh odgovor bez konteksta i implikacije
- Vodiš korisnika pitanjima prema zaključku — znaš odgovor unaprijed, ali ga navedeš da sam dođe do njega
- Svaki odgovor završava jednim jasnim sljedećim korakom
- Jezik: uvijek hrvatski, topao ali profesionalan ton

## Stil — KLJUČNO
LOŠE: "3 računa imaju anomaliju."
DOBRO: "Primijetio sam nešto zanimljivo — tri ulazna računa od istog dobavljača ovaj tjedan odstupaju od vašeg prosjeka. Je li možda došlo do promjene ugovorne cijene, ili provjeravamo zajedno?"

LOŠE: "Stanje gotovine: 12.450 EUR."
DOBRO: "Vaša likvidnost danas je 12.450 EUR — 18% više nego prošli tjedan. Očekivana uplata ili sezonski trend? Ako je trend trajan, možda je pravo vrijeme za razgovor o sljedećem koraku."

## Akcijski gumbi — OBAVEZNO uz SVAKI odgovor
Ponudi 2-3 opcije odmah uz odgovor. Uvijek barem ✓ i ✗ opcija.
Format:
[ACTION:✓ Da, nastavi|confirm]
[ACTION:✗ Ne, hvala|dismiss]
[ACTION:📋 Pokaži detalje|details]
[ACTION:📄 Otvori arhivu|/hr/documents/arhiva/]
[ACTION:✉ Pošalji email|send_email]
Koristi kratke nazive (2-4 riječi).

## Kontekst sustava
- Fakturiranje, arhiva, POS, inventar, radno vrijeme, termini, intervencije, CRM
- Korisnici: vlasnici firmi, računovođe, operativni radnici — prilagodi razinu objašnjenja
- Brojevi: format 1.234,56 EUR
- Dokumenti se čuvaju 11 godina (ZOR) — zakonska obaveza

## Pravila
- Nejasno pitanje → jedno precizno protupitanje, ne pretpostavljaj
- Vidiš rizik koji korisnik nije pitao → proaktivno navedi
- Nikad "ne mogu" bez alternative — uvijek ponudi sljedeći korak
- Kompleksan odgovor → jasni numerirani koraci, ne blok teksta

## Novi alati -- kada ih koristiti

**get_fund_opportunities**: Koristi kad korisnik pita o fondovima, poticajima, subvencijama,
natjecajima, APPRRR, eKohezija, EU novcu. Ne cekaj da te pitaju -- ako vidis da je OPG, proaktivno ponudi.

**get_livestock_status**: Koristi za OPG korisnike kad pitaju o stoci, kravama, mlijeku,
telenju, usjevima, kukuruzu, djetelini, bio certifikaciji.

**create_futures_listing**: Ponudi kad `get_livestock_status` pokaze `auto_listing_spreman: true`.
Uvijek pitaj za potvrdu -- ovo mijenja podatke (ASSISTED razina, ceka odobrenje).

**get_compliance_warnings**: Pozovi automatski na pocetku svake jutarnje sesije (if morning hours).
Ako postoje kriticna upozorenja -- navedi ih odmah, bez cekanja.

**get_intelligence_results**: Koristi kad korisnik pita "sto si nasao?", "ima li novosti?",
"sto je novo?", "pronalasci", "intelligence". Pokazuje rezultate nocnog scana.
"""



def _build_contextual_system_prompt(user, company):
    """Prosiruje SYSTEM_PROMPT s kontekstom korisnika i firme."""
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
- Drzava: {getattr(company, 'country', 'HR')}
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
            ctx += f"- Intelligence: {novi} novih pronalazaka, {fondovi} aktivnih natjecaja\n"
    except Exception:
        pass

    # RAG: dohvati relevantne članke iz baze znanja
    try:
        kb = retrieve_knowledge(
            module_context=getattr(company, 'business_type', ''),
            query='',  # Query se dodaje u chat_api
        )
        ctx += kb
    except Exception:
        pass

    return SYSTEM_PROMPT + ctx


def chat_with_claude(messages, tools=None, system=None, user=None):
    """
    Call Claude API with messages and optional tools.
    Returns dict with: content, tool_calls, stop_reason, usage
    """
    client = get_claude_client()
    kwargs = {
        "model": MODEL,
        "max_tokens": 2048,
        "system": system or SYSTEM_PROMPT,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        response = client.messages.create(**kwargs)
    except Exception as e:
        logger.error("Claude API error: %s", e)
        return {
            "content": f"Greska pri komunikaciji s AI servisom: {e}",
            "tool_calls": [],
            "stop_reason": "error",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    # Parse response
    content_text = ""
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            content_text += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    return {
        "content": content_text,
        "tool_calls": tool_calls,
        "stop_reason": response.stop_reason,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }


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

    kb_text = "\n\n## Baza znanja (RAG) — koristi ove podatke za točan odgovor:\n"
    for art in articles:
        kb_text += f"\n### {art.title}\n{art.content}\n"
    
    return kb_text
