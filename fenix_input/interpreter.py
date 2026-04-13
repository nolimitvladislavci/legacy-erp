"""
fenix_input/interpreter.py — AI interpretacija ulaznih poruka

Pero kaže: "Košnica tri, dvanaest kila, tretirao oksalnom"
AI vraća: {intent: "bee_log", target_module: "livestock",
           fields: {hive_id: 3, weight_kg: 12, treatment: "oksalna kiselina"},
           confidence: 0.95}
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger('fenix_input')

# Kontekst za AI — što sustav podržava
SYSTEM_PROMPT = """Ti si AI asistent za LIMIT Connect ERP sustav.
Tvoj posao je parsirati prirodni jezik (govor, SMS, email) u strukturirane podatke.

MODULI KOJE PODRŽAVAŠ:
- livestock: Evidencija stoke/farme. Akcije: log_weight, log_health, log_milk, update_status
- memio_pet: Profili ljubimaca. Akcije: add_animal, update_status, log_health
- inventory: Skladište/artikli. Akcije: add_stock, remove_stock, count_stock
- pos: Blagajna. Akcije: log_sale, daily_report
- worktime: Radno vrijeme. Akcije: clock_in, clock_out, log_hours
- beekeeping: Pčelarstvo (unutar livestock). Akcije: log_hive_weight, log_treatment, log_harvest, log_inspection

PRAVILA:
1. Odgovori SAMO s JSON objektom, bez teksta
2. Polja: intent (string), target_module (string), target_action (string), fields (object), confidence (0-1)
3. Ako ne možeš parsirati → confidence < 0.3, intent: "unknown"
4. Brojeve pretvori u numeričke tipove
5. Datume u ISO format (YYYY-MM-DD)
6. Prepoznaj hrvatske izraze: oksalna = oksalna kiselina, tretirao = treatment, kila = kg

PRIMJERI:
Ulaz: "Košnica tri, dvanaest kila, tretirao oksalnom"
→ {"intent": "bee_log", "target_module": "livestock", "target_action": "log_hive_weight",
   "fields": {"hive_id": 3, "weight_kg": 12.0, "treatment": "oksalna kiselina"}, "confidence": 0.95}

Ulaz: "W:12.3kg T:21C H:65% BAT:92%"
→ {"intent": "sensor_reading", "target_module": "livestock", "target_action": "log_hive_weight",
   "fields": {"weight_kg": 12.3, "temperature_c": 21.0, "humidity_pct": 65, "battery_pct": 92}, "confidence": 0.98}

Ulaz: "Rex je dobio cjepivo protiv bjesnoće"
→ {"intent": "pet_health", "target_module": "memio_pet", "target_action": "log_health",
   "fields": {"animal_name": "Rex", "record_type": "vaccination", "description": "cjepivo protiv bjesnoće"}, "confidence": 0.9}
"""


def interpret_message(raw_text, channel='voice', user=None, company=None):
    """
    Šalje tekst Claude API-ju za interpretaciju.
    Vraća dict s parsiranim podacima.
    """
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Dodaj kontekst korisnika/firme
        user_context = ""
        if company:
            user_context += f"\nFirma: {company.name} (tip: {getattr(company, 'company_type', 'unknown')})"
        if user:
            user_context += f"\nKorisnik: {user.get_full_name() or user.username}"
        if channel == 'sms':
            user_context += "\nKanal: SMS od IoT uređaja — očekuj strukturirane senzorske podatke"
        elif channel == 'voice':
            user_context += "\nKanal: Glasovni unos — prirodni jezik, moguće greške u transkripciji"

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM_PROMPT + user_context,
            messages=[{"role": "user", "content": raw_text}],
        )

        result_text = response.content[0].text.strip()
        # Očisti markdown wrapping ako postoji
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        parsed = json.loads(result_text)
        logger.info(f'AI interpreted [{channel}]: {raw_text[:50]}... → {parsed.get("intent")} (conf={parsed.get("confidence")})')
        return parsed

    except json.JSONDecodeError as e:
        logger.warning(f'AI returned invalid JSON: {e}')
        return {'intent': 'parse_error', 'confidence': 0, 'error': str(e)}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'AI interpretation failed: {e}')
        return {'intent': 'error', 'confidence': 0, 'error': str(e)}


def parse_sms_by_pattern(raw_text, pattern):
    """
    Fallback: parsira SMS po regex patternu uređaja.
    Brže od AI-a, za poznate formate senzora.
    """
    import re
    if not pattern:
        return None
    match = re.search(pattern, raw_text)
    if match:
        return match.groupdict()
    return None
