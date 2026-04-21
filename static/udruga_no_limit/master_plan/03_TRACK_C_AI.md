# TRAK C — AI / RESOLVER / INTENT

**Vlasnik**: AI agent
**File područje**: `core/resolver/` (NOVO), `core/intent_compiler/` (NOVO), `core/ambient/` (NOVO), `core/whisper_local/` (NOVO)
**NE diraj**: UI templates, baze (osim `intent_definition` tablice koju kreira Trak A)

---

## CILJ

Pretvoriti svaki ulazni signal (text, voice transcript, image OCR) u **strukturiranu akciju** koja pokreće postojeći Django view ili API.

```
Input (text/voice/image) → Intent Classifier → Slot Filling → Handler → Output
                                ↓
                          (ako fail) → Haiku fallback → Handler → Output
```

---

## SPRINT 1 — Resolver API endpoint (T3, parallelno s Trak B Sprint 1)

### Akcija C1.1 — `/api/cmd/resolve/` Django view

```python
# core/resolver/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@login_required
@require_POST
def resolve(request):
    payload = json.loads(request.body)
    text = payload.get("text", "")
    context = payload.get("context", "ucs")  # ucs ili pos
    user = request.user

    from core.resolver.classifier import classify_intent
    from core.resolver.slot_filler import fill_slots
    from core.resolver.dispatcher import dispatch

    intent_name, confidence = classify_intent(text, context=context, user=user)

    if confidence < 0.7:
        # Fallback na Haiku
        from core.resolver.haiku_fallback import haiku_resolve
        return JsonResponse(haiku_resolve(text, user, context))

    slots = fill_slots(text, intent_name)
    result = dispatch(intent_name, slots, user, context)
    return JsonResponse(result)
```

### Akcija C1.2 — Lightweight intent classifier (sklearn LR)

```python
# core/resolver/classifier.py
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

_model = None

def get_model():
    global _model
    if _model is None:
        _model = joblib.load("/var/www/fenix-v3/models/intent_classifier.pkl")
    return _model

def classify_intent(text, context="ucs", user=None):
    model = get_model()
    proba = model.predict_proba([text])[0]
    best_idx = proba.argmax()
    return model.classes_[best_idx], proba[best_idx]
```

### Akcija C1.3 — Trening intent classifier-a (jednom)

```python
# core/resolver/train.py
# Trening dataset: 50–100 primjera po intentu × 20 intenta = 1000–2000 primjera
TRAINING_DATA = [
    ("napravi račun za nikolić", "create_invoice"),
    ("kreiraj fakturu nikolić", "create_invoice"),
    ("novi račun nikolić", "create_invoice"),
    ("pripremi pdv nikolić", "prepare_pdv"),
    ("pdv obrazac za nikolić", "prepare_pdv"),
    ("pdv q1 nikolić", "prepare_pdv"),
    # ... 1000+ primjera
]

def train():
    texts = [t[0] for t in TRAINING_DATA]
    labels = [t[1] for t in TRAINING_DATA]
    vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1)
    X = vectorizer.fit_transform(texts)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)
    joblib.dump((vectorizer, clf), "models/intent_classifier.pkl")
```

### Akcija C1.4 — Slot filler (regex + named entity)

```python
# core/resolver/slot_filler.py
import re

INTENT_SCHEMAS = {
    "create_invoice": {
        "company": r"(?:za|kupcu|klijentu)\s+(.+?)(?:\s|$)",
        "amount": r"(\d+(?:[.,]\d+)?)\s*(?:eur|€|kn|kuna)?",
    },
    "prepare_pdv": {
        "company": r"(?:za|kupcu)\s+(.+?)(?:\s|$)",
        "period": r"(q[1-4])\s*(\d{4})?",
    },
}

def fill_slots(text, intent_name):
    schema = INTENT_SCHEMAS.get(intent_name, {})
    slots = {}
    for slot_name, pattern in schema.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            slots[slot_name] = match.group(1).strip()
    return slots
```

---

## SPRINT 2 — Haiku Fallback + Ambient AI (T4–T5)

### Akcija C2.1 — Haiku fallback (5% upita, niskog confidence)

```python
# core/resolver/haiku_fallback.py
from anthropic import Anthropic

client = Anthropic()

def haiku_resolve(text, user, context):
    prompt = f"""Korisnik je upisao: '{text}'
Kontekst: {context}
Dostupni intent-i: create_invoice, prepare_pdv, find_company, ...

Vrati JSON:
{{
  "intent": "...",
  "slots": {{"company": "...", ...}},
  "confidence": 0.0-1.0,
  "human_reply": "..."
}}"""
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(msg.content[0].text)
```

### Akcija C2.2 — Ambient AI predictor

```python
# core/ambient/predictor.py
def get_suggestions(user, max_n=3):
    """Vraća 3 najvjerojatnije akcije za korisnika u ovom trenutku."""
    # Inputi: vrijeme, dan, kalendar, neprošle notifikacije, recent actions
    # Output: lista action proposals
    suggestions = []

    # 1. Regulatorni rokovi (PDV, JOPPD, GFI)
    suggestions += check_regulatory_deadlines(user)

    # 2. Neprošle notifikacije
    suggestions += check_pending_notifications(user)

    # 3. Recurring actions (npr. mjesečni račun za najam)
    suggestions += check_recurring_patterns(user)

    return sorted(suggestions, key=lambda s: -s["urgency"])[:max_n]
```

---

## SPRINT 3 — Whisper lokalni + multi-item kamera (T6–T7)

### Akcija C3.1 — Whisper.cpp lokalni endpoint

```python
# core/whisper_local/views.py
import subprocess
import tempfile

@require_POST
def transcribe(request):
    audio_file = request.FILES['audio']
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(audio_file.read())
        path = f.name
    result = subprocess.run(
        ['/opt/whisper.cpp/main', '-m', '/opt/whisper.cpp/models/ggml-medium.bin',
         '-l', 'hr', '-f', path, '-otxt'],
        capture_output=True, text=True
    )
    transcript = result.stdout.strip()
    return JsonResponse({"text": transcript})
```

### Akcija C3.2 — Multi-item Vision (Gemini API)

```python
# core/resolver/vision.py
import google.generativeai as genai

def detect_items_in_image(image_bytes):
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content([
        "Detektiraj sve proizvode na slici. Vrati JSON listu: [{name, quantity, confidence}].",
        {"mime_type": "image/jpeg", "data": image_bytes}
    ])
    return json.loads(response.text)
```

---

## INTENT REGISTRY (početni 20)

Kreirati u `intent_definition` tablici (Trak A):

| # | name | example_phrases | handler_path |
|---|---|---|---|
| 1 | create_invoice | „napravi račun", „nova faktura" | `invoicing.views.create_invoice` |
| 2 | prepare_pdv | „pripremi pdv", „pdv obrazac" | `accounting.views.pdv_form` |
| 3 | find_company | „pronađi firmu", „nađi kupca" | `companies.views.search` |
| 4 | upload_archive | „arhiviraj", „spremi u arhivu" | `arhiva.views.upload` |
| 5 | scan_receipt | „skeniraj račun" | `arhiva.views.smart_import` |
| 6 | pos_add_item | „dodaj coca colu", „dodaj kruh" | `pos.views.add_item` |
| 7 | pos_total | „total", „izračunaj" | `pos.views.show_total` |
| 8 | pos_pay | „naplati karticom/gotovinom" | `pos.views.checkout` |
| 9 | check_balance | „koliko ima na računu" | `accounting.views.balance` |
| 10 | list_overdue | „neplaćeni računi" | `invoicing.views.overdue` |
| ... | ... | ... | ... |

---

## SLJEDEĆA AKCIJA

→ **C1.1**: postavi `/api/cmd/resolve/` endpoint (samo skeleton, vraća dummy). Trak B može početi paralelno.

## ZADNJA IZMJENA

| Datum | Tko | Što | Sljedeći korak |
|---|---|---|---|
| 21.04.2026. | Opus design | Plan napisan | C1.1 endpoint |


---

## CIRCUIT BREAKER + FALLBACK STACK (Načelo #11)

### Razina 1 → 2 → 3 → 4 fallback chain

```python
# core/resolver/dispatcher.py
from core.resolver.circuit_breaker import circuit_breaker

@circuit_breaker(failure_threshold=3, timeout=5, recovery_timeout=60)
def resolve_with_fallback(text, context, user):
    """Pokušaj sve razine dok jedna ne uspije."""
    
    # RAZINA 1: Haiku (cloud, najpametniji)
    try:
        return haiku_resolve(text, context, user)
    except (TimeoutError, APIError, ConnectionError) as e:
        logger.warning(f"Haiku fail: {e}")
    
    # RAZINA 2: Lokalni SLM (Phi-3 mini, offline OK)
    try:
        return local_slm_resolve(text, context, user)
    except Exception as e:
        logger.warning(f"Local SLM fail: {e}")
    
    # RAZINA 3: Regex intent matcher (deterministic)
    try:
        return regex_intent_resolve(text, context, user)
    except Exception as e:
        logger.warning(f"Regex fail: {e}")
    
    # RAZINA 4: vrati URL na klasični UI
    return {
        "intent": "fallback_to_classic",
        "redirect_url": classic_url_for_context(context),
        "message": "AI nije dostupan. Otvori klasični prikaz."
    }
```

### Lokalni SLM setup

```bash
# Instalacija Phi-3 mini (3.8B, ~2 GB VRAM ili 4 GB RAM CPU)
pip install llama-cpp-python
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
mv Phi-3-mini-4k-instruct-q4.gguf /opt/models/
```

```python
# core/resolver/local_slm.py
from llama_cpp import Llama

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path="/opt/models/Phi-3-mini-4k-instruct-q4.gguf",
            n_ctx=2048, n_threads=4
        )
    return _llm

def local_slm_resolve(text, context, user):
    prompt = f"""Korisnik je upisao: '{text}'
Vrati JSON s intent + slots."""
    response = get_llm()(prompt, max_tokens=200, temperature=0.1)
    return parse_json_safely(response['choices'][0]['text'])
```

**Brzina**: Phi-3 mini na CPU (4 jezgre) = ~200–400ms po pozivu. Nema API troška. Radi offline.

### Telemetrija

```python
# Za svaku resolve(), zapisuj koja razina je odgovorila:
metrics.increment(f"resolve.level_{level_used}")
metrics.gauge(f"resolve.latency_ms.level_{level_used}", duration)
```

Cilj: > 95% RAZINA 1 (Haiku radi), < 4% RAZINA 2 (lokalni), < 1% RAZINE 3-4 (degraded).

### Što kad SVE pada

Svi 4 razine fail = vraća user na `/classic/...` URL. Klasični UI radi 100% (ne ovisi o AI-u). User može nastaviti raditi kao danas.

## DEPENDENCIES

- **Čeka**: S1 (Trak A — Searchable mixin za pretragu firmi)
- **Blokira**: Trak B Sprint 1 (treba endpoint)
