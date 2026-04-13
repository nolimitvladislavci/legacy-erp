"""
eracun/services/ai_config_parser.py
AI-powered parser for posrednik configuration.
Extracts API keys, URLs, credentials from emails/documents.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_posrednik_config(text):
    """
    Parse posrednik configuration from free-text (email, document, copy-paste).
    Returns dict with extracted fields.
    Works WITHOUT AI — pure regex. AI version below as enhancement.
    """
    result = {
        'posrednik_type': '',
        'posrednik_api_url': '',
        'posrednik_api_key': '',
        'posrednik_api_secret': '',
        'posrednik_username': '',
        'posrednik_password': '',
        'posrednik_company_id': '',
    }

    text_lower = text.lower()

    # Detect posrednik type
    if 'fina' in text_lower and ('peppol' in text_lower or 'eracun' in text_lower or 'e-racun' in text_lower):
        result['posrednik_type'] = 'fina'
    elif 'moj-eracun' in text_lower or 'mojeracun' in text_lower or 'moj eracun' in text_lower:
        result['posrednik_type'] = 'moj_eracun'
    elif 'pondi' in text_lower or 'eposlovanje' in text_lower:
        result['posrednik_type'] = 'pondi'
    else:
        result['posrednik_type'] = 'custom'

    # Extract URLs
    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    api_urls = [u for u in urls if 'api' in u.lower() or 'endpoint' in u.lower() or 'service' in u.lower()]
    if api_urls:
        result['posrednik_api_url'] = api_urls[0]
    elif urls:
        result['posrednik_api_url'] = urls[0]

    # Extract API key patterns
    key_patterns = [
        r'(?:api[_-]?key|token|bearer|kljuc|key)\s*[:=]\s*["\'\s]*([A-Za-z0-9_\-\.]{20,})',
        r'(?:Authorization|Auth)\s*[:=]\s*(?:Bearer\s+)?["\'\s]*([A-Za-z0-9_\-\.]{20,})',
    ]
    for pat in key_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['posrednik_api_key'] = m.group(1).strip().strip("\"\'")
            break

    # Extract secret
    secret_patterns = [
        r'(?:secret|tajni[_\s]?kljuc|client[_\s]?secret)\s*[:=]\s*["\'\s]*([A-Za-z0-9_\-\.]{10,})',
    ]
    for pat in secret_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['posrednik_api_secret'] = m.group(1).strip().strip("\"\'")
            break

    # Extract username
    user_patterns = [
        r'(?:username|korisnik|user|login|korisnicko[_\s]ime)\s*[:=]\s*["\'\s]*([^\s<>\"]{3,50})',
    ]
    for pat in user_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['posrednik_username'] = m.group(1).strip().strip("\"\'")
            break

    # Extract password
    pwd_patterns = [
        r'(?:password|lozinka|pass|pwd|geslo)\s*[:=]\s*["\'\s]*([^\s<>\"]{4,50})',
    ]
    for pat in pwd_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['posrednik_password'] = m.group(1).strip().strip("\"\'")
            break

    # Extract company/participant ID
    id_patterns = [
        r'(?:participant[_\s]?id|company[_\s]?id|peppol[_\s]?id|id[_\s]?firme|identifikator)\s*[:=]\s*["\'\s]*([A-Za-z0-9:_\-]{5,50})',
        r'(?:0192|9934):[0-9]{11}',  # Peppol participant ID format
    ]
    for pat in id_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1) if m.lastindex else m.group(0)
            result['posrednik_company_id'] = val.strip().strip("\"\'")
            break

    # Extract OIB if present
    oib_match = re.search(r'OIB\s*[:=]?\s*(\d{11})', text)
    if oib_match:
        result['_oib'] = oib_match.group(1)

    # Confidence score
    filled = sum(1 for v in result.values() if v and v != 'custom')
    result['_confidence'] = round(filled / 7, 2)
    result['_source'] = 'regex_parser'

    return result


def parse_posrednik_config_ai(text):
    """
    AI-enhanced parser — uses Gemini to extract structured data from
    posrednik onboarding emails/documents.
    Falls back to regex parser if AI unavailable.
    """
    try:
        import os

        import google.generativeai as genai

        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return parse_posrednik_config(text)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""Iz sljedeceg teksta izvuci podatke za konfiguraciju e-racun posrednika.
Vrati SAMO JSON bez markdown formatiranja, sa ovim poljima:
- posrednik_type: "fina", "moj_eracun", "pondi", ili "custom"
- posrednik_api_url: API endpoint URL
- posrednik_api_key: API kljuc/token
- posrednik_api_secret: API secret (ako postoji)
- posrednik_username: korisnicko ime
- posrednik_password: lozinka
- posrednik_company_id: ID firme ili Peppol participant ID

Ako neko polje ne postoji u tekstu, ostavi prazan string "".

TEKST:
{text[:3000]}"""

        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Clean markdown
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3]
        if raw.startswith('json'):
            raw = raw[4:]

        result = json.loads(raw.strip())
        result['_confidence'] = 0.9
        result['_source'] = 'gemini_ai'
        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f'AI config parser failed: {e}, falling back to regex')
        return parse_posrednik_config(text)
