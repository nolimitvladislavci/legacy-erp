"""
Borg Advisor Light — AI plan preporuka za registraciju.
Koristi Haiku (brzo, jeftino). Fallback na keyword matching.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Keyword→plan mapping (fallback bez AI-a)
KEYWORD_PLAN_MAP = {
    'starter': [
        'obrt', 'obrtar', 'opg', 'poljoprivred', 'kosilar', 'čišćen',
        'vodoinstalat', 'elektricar', 'zidar', 'medicinska sestra', 'frizjer',
        'kozmetičar', 'cvjetar', 'ribar', 'pčelar', 'vinogradar',
        'prijevoznik', 'taksist', 'autolimar', 'bravar', 'stolar',
        'keramičar', 'soboslikar', 'dimnjačar', 'fotograf',
    ],
    'professional': [
        'restoran', 'kafić', 'caffe', 'hotel', 'smještaj', 'apartman',
        'servis', 'automehaničar', 'vulkanizer', 'računovodstvo', 'knjig',
        'agencija', 'građevinar', 'prijevoz', 'veterinar', 'ljekarnar',
        'prodavaonica', 'maloprodaja', 'veleprodaja', 'pekara', 'mesnica',
        'slastičarna', 'pizzeria', 'bistro', 'konoba', 'fast food',
        'salon', 'studio', 'ordinacija', 'klinika', 'ambulanta',
    ],
    'enterprise': [
        'komunal', 'grad', 'općina', 'dom zdravlja', 'bolnica', 'škola',
        'vrtić', 'lječilište', 'holding', 'grupa', 'd.d.', 'dioničko',
        'franšiza', 'distributer', 'umbrella', 'udruga', 'zadruga',
        'neprofitna', 'fondacija', 'zavod', 'ustanova', 'institut',
    ],
}

PLAN_REASONS = {
    'starter': 'Savršen za obrte i OPG-ove — fiskalizacija i fakture u džepu.',
    'professional': 'Idealan za vašu djelatnost — tim, AI asistent i WhatsApp uključeni.',
    'enterprise': 'Za organizacije koje trebaju napredne module i neograničene korisnike.',
}


def recommend_plan_by_keyword(name: str, industry: str = '') -> dict:
    """Brza keyword preporuka — uvijek radi, 0ms."""
    text = (name + ' ' + industry).lower()
    scores = {'starter': 0, 'professional': 0, 'enterprise': 0}
    for plan, keywords in KEYWORD_PLAN_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[plan] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = 'professional'  # Default za nepoznate
    return {
        'plan': best,
        'confidence': 'keyword',
        'reason': PLAN_REASONS.get(best, ''),
    }


def recommend_plan_ai(name: str, nkd: str = '') -> dict:
    """
    AI preporuka plana — Haiku, sync (< 2s).
    Fallback na keyword ako Haiku ne odgovori.
    """
    fallback = recommend_plan_by_keyword(name, nkd)

    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        return fallback

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"Tvrtka se želi registrirati na LIMIT Connect ERP.\n"
            f"Naziv: {name}\n"
            f"NKD/djelatnost: {nkd or 'nije poznato'}\n\n"
            "LIMIT Connect planovi:\n"
            "- starter (9 EUR/mj): fiskalizacija, fakture, POS, 1 korisnik — za obrte i OPG\n"
            "- professional (29 EUR/mj): sve + radni sati, AI, WhatsApp, 5 korisnika — za tvrtke s timom\n"
            "- enterprise (79 EUR/mj): sve + neograničeno, komunale, udruge, multi-firma\n\n"
            'Odgovori SAMO JSON-om:\n'
            '{"plan": "starter|professional|enterprise", "reason": "jedna rečenica zašto (na hrvatskom)"}'
        )

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=100,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text.strip()
        data = json.loads(raw)
        if data.get('plan') in ('starter', 'professional', 'enterprise'):
            return {
                'plan': data['plan'],
                'confidence': 'ai',
                'reason': data.get('reason', ''),
            }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning('Borg Advisor AI fallback: %s', e)

    return fallback
