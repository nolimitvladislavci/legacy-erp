"""
AI Service Agent — Human-in-the-loop email/message handler.

Flow:
  1. Inbound message arrives (email/WhatsApp/portal)
  2. AI analyzes: sentiment, category, image analysis
  3. AI generates draft reply
  4. Draft appears in dashboard for human approval
  5. Human approves/edits → message sent
  6. BookingSignature audit trail on every action

Uses Anthropic Claude for text analysis and Gemini for multimodal (images).
Falls back gracefully if neither is available.
"""
import base64
import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('stolarija')


# ═══════════════════════════════════════════════════════════════════════════
# SENTIMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

# Rule-based sentiment as fallback (no API needed)
NEGATIVE_SIGNALS = [
    'reklamacija', 'prokišnjava', 'propušta', 'ne radi', 'pokvaren',
    'razočaran', 'razocaran', 'ljut', 'bijesan', 'skandal', 'tužba', 'tuzba',
    'odvjetnik', 'inspekcija', 'nedopustivo', 'katastrofa', 'užas', 'uzas',
    'nikad više', 'nikad vise', 'žalba', 'zalba', 'povrat novca',
    'škripi', 'skripi', 'puklo', 'slomljeno', 'razbijeno',
    'smrzavamo', 'prokisnjavamo', 'curi', 'pušta', 'pusta',
]
URGENT_SIGNALS = [
    'hitno', 'odmah', 'žurno', 'zurno', 'opasnost', 'sigurnost',
    'dijete', 'hladnoća', 'hladnoca', 'poplava', 'voda ulazi',
]
POSITIVE_SIGNALS = [
    'hvala', 'odlično', 'odlicno', 'super', 'zadovoljan', 'preporuka',
    'bravo', 'savršeno', 'savrseno', 'profesionalno',
]


def analyze_sentiment(text: str) -> str:
    """Rule-based sentiment analysis. Returns: positive/neutral/negative/urgent."""
    text_lower = text.lower()

    if any(w in text_lower for w in URGENT_SIGNALS):
        return 'urgent'
    neg_count = sum(1 for w in NEGATIVE_SIGNALS if w in text_lower)
    pos_count = sum(1 for w in POSITIVE_SIGNALS if w in text_lower)

    if neg_count >= 2:
        return 'negative'
    if neg_count == 1 and pos_count == 0:
        return 'negative'
    if pos_count >= 2:
        return 'positive'
    return 'neutral'


def categorize_message(text: str) -> str:
    """Categorize inbound message. Returns: complaint/service_request/info/scheduling."""
    text_lower = text.lower()

    scheduling_words = ['termin', 'dogovor', 'kada', 'kad', 'datum', 'slobodn',
                        'zakazati', 'doći', 'doci', 'posjeta']
    complaint_words = ['reklamacija', 'žalba', 'zalba', 'ne radi', 'problem',
                       'kvar', 'defekt', 'pokvaren', 'garancij']
    service_words = ['servis', 'pregled', 'podmazati', 'podesiti', 'održavanje',
                     'odrzavanje', 'zamjena', 'brtva', 'okov']

    if any(w in text_lower for w in complaint_words):
        return 'complaint'
    if any(w in text_lower for w in scheduling_words):
        return 'scheduling'
    if any(w in text_lower for w in service_words):
        return 'service_request'
    return 'info'


# ═══════════════════════════════════════════════════════════════════════════
# IMAGE ANALYSIS (Multimodal)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_image(image_bytes: bytes, context: str = '') -> dict:
    """
    Analyze window/door image using AI vision.
    Returns: {description, issues_found, severity, confidence}
    """
    result = {
        'description': '',
        'issues_found': [],
        'severity': 'unknown',
        'confidence': 0.0,
        'model_used': 'none',
    }

    # Try Anthropic Claude first
    try:
        import anthropic
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            b64 = base64.b64encode(image_bytes).decode()

            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=500,
                messages=[{
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64},
                        },
                        {
                            'type': 'text',
                            'text': (
                                'Analiziraj ovu sliku prozora/vrata/stolarije. '
                                'Odgovori JSON formatom: '
                                '{"description": "opis što se vidi", '
                                '"issues_found": ["problem1", "problem2"], '
                                '"severity": "none/minor/moderate/severe", '
                                '"confidence": 0.0-1.0}. '
                                f'Kontekst: {context}'
                            ),
                        },
                    ],
                }],
            )

            text = response.content[0].text
            # Parse JSON from response
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                result.update(parsed)
                result['model_used'] = 'claude-haiku'
                return result

    except Exception as e:
        logger.warning('Image analysis (Anthropic) failed: %s', e)

    # Fallback: no analysis available
    result['description'] = 'Automatska analiza slike nije dostupna.'
    result['confidence'] = 0.0
    return result


# ═══════════════════════════════════════════════════════════════════════════
# DRAFT GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_draft_reply(message) -> dict:
    """
    Generate AI draft reply for an inbound ServiceMessage.
    Returns: {draft: str, sentiment: str, category: str, confidence: float}
    """
    sentiment = analyze_sentiment(message.body)
    category = categorize_message(message.body)

    # Build context
    warranty_info = ''
    if message.warranty:
        w = message.warranty
        warranty_info = (
            f"Garancija: {w.warranty_number}, "
            f"Primopredaja: {w.handover_date or '—'}, "
            f"Trajanje: {w.valid_years}g, "
            f"Adresa: {w.session.address if w.session else '—'}"
        )
        risk = getattr(w, 'risk_profile', None)
        if risk:
            warranty_info += f", Risk: {risk.risk_score}/100 ({risk.get_risk_level_display()})"

    # Try LLM draft
    draft = _generate_llm_draft(message, sentiment, category, warranty_info)

    # Fallback to template-based draft
    if not draft:
        draft = _generate_template_draft(message, sentiment, category, warranty_info)

    return {
        'draft': draft,
        'sentiment': sentiment,
        'category': category,
        'confidence': 0.8 if draft else 0.3,
    }


def _generate_llm_draft(message, sentiment, category, warranty_info) -> str:
    """Try to generate draft via LLM API."""
    try:
        import anthropic
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key:
            return ''

        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = (
            'Ti si AI asistent za servis stolarije (prozori, vrata). '
            'Pišeš profesionalne, ljubazne odgovore na hrvatskom jeziku. '
            'Potpis: "Vaš Fenix AI asistent — LIMIT Connect". '
            'NIKADA ne obećavaj fiksne termine — uvijek dodaj "Termin će biti potvrđen od strane našeg ureda". '
            'Ako je kupac ljut, budi empatiačn i eskaliraj: "Vaš slučaj je proslijeđen voditelju servisa". '
            'Drži odgovor kratak — max 150 riječi.'
        )

        user_prompt = (
            f"Kupac je poslao poruku.\n"
            f"Sentiment: {sentiment}\n"
            f"Kategorija: {category}\n"
            f"Garancija: {warranty_info or 'Nepoznata'}\n\n"
            f"Poruka kupca:\n{message.body}\n\n"
            f"Napiši profesionalan odgovor."
        )

        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        return response.content[0].text.strip()

    except Exception as e:
        logger.warning('LLM draft generation failed: %s', e)
        return ''


def _generate_template_draft(message, sentiment, category, warranty_info) -> str:
    """Fallback: template-based draft when LLM is unavailable."""
    name = message.sender_name or 'cijenjeni kupče'

    if sentiment == 'urgent':
        return (
            f"Poštovani {name},\n\n"
            f"Zaprimili smo Vašu hitnu poruku i razumijemo ozbiljnost situacije. "
            f"Vaš slučaj je proslijeđen voditelju servisa koji će Vas kontaktirati "
            f"u najkraćem mogućem roku.\n\n"
            f"Vaš Fenix AI asistent — LIMIT Connect"
        )

    if sentiment == 'negative':
        return (
            f"Poštovani {name},\n\n"
            f"Žao nam je zbog neugodnosti. Vaš slučaj je zabilježen i proslijeđen "
            f"voditelju servisa. Javit ćemo Vam se u roku od 24 sata s prijedlogom rješenja.\n\n"
            f"Vaš Fenix AI asistent — LIMIT Connect"
        )

    if category == 'scheduling':
        return (
            f"Poštovani {name},\n\n"
            f"Hvala na upitu za termin servisnog pregleda. "
            f"Provjerit ćemo dostupnost i javiti Vam se s prijedlogom termina. "
            f"Termin će biti potvrđen od strane našeg ureda.\n\n"
            f"Vaš Fenix AI asistent — LIMIT Connect"
        )

    if category == 'service_request':
        return (
            f"Poštovani {name},\n\n"
            f"Hvala na prijavi. Zabilježili smo Vaš zahtjev za servis. "
            f"Naš tehničar će pregledati detalje i predložiti termin pregleda. "
            f"Termin će biti potvrđen od strane našeg ureda.\n\n"
            f"Vaš Fenix AI asistent — LIMIT Connect"
        )

    if category == 'complaint':
        return (
            f"Poštovani {name},\n\n"
            f"Zaprimili smo Vašu reklamaciju i ozbiljno je shvaćamo. "
            f"Vaš slučaj je proslijeđen voditelju servisa koji će Vas kontaktirati "
            f"u roku od 24 sata.\n\n"
            f"Vaš Fenix AI asistent — LIMIT Connect"
        )

    return (
        f"Poštovani {name},\n\n"
        f"Hvala na poruci. Zabilježili smo Vaš upit i javit ćemo Vam se "
        f"u najkraćem mogućem roku.\n\n"
        f"Vaš Fenix AI asistent — LIMIT Connect"
    )


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE PROCESSING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def process_inbound_message(message) -> None:
    """
    Full pipeline for an inbound ServiceMessage.
    1. Sentiment + category analysis
    2. Image analysis (if attachment)
    3. Warranty matching
    4. Draft generation
    5. Auto-escalate if negative/urgent
    """
    # Analyze
    result = generate_draft_reply(message)
    message.ai_sentiment = result['sentiment']
    message.ai_category = result['category']
    message.ai_draft = result['draft']
    message.ai_confidence = result['confidence']

    # Image analysis
    if message.attachment:
        try:
            image_bytes = message.attachment.read()
            if image_bytes and len(image_bytes) < 5_000_000:
                img_result = analyze_image(
                    image_bytes,
                    context=f"Warranty: {message.warranty}, Message: {message.body[:200]}"
                )
                message.ai_image_analysis = img_result
        except Exception as e:
            logger.warning('Image analysis failed for message %s: %s', message.pk, e)

    # Auto-escalate
    if result['sentiment'] in ('negative', 'urgent'):
        message.status = 'escalated'
    else:
        message.status = 'ai_draft'

    message.save(update_fields=[
        'ai_sentiment', 'ai_category', 'ai_draft',
        'ai_confidence', 'ai_image_analysis', 'status',
    ])

    logger.info(
        'Processed message %s: sentiment=%s, category=%s, status=%s',
        message.pk, result['sentiment'], result['category'], message.status
    )
