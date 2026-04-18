# PLAN_055 — Voice Input (Web Speech API — Glasovni Unos)

## Cilj
Glasovni unos za accessibility-first dizajn. Korisnici koji imaju motoričke poteškoće ili rade s rukama mogu govorom diktirati unos. Web Speech API (browser-native, 0 servera). Integracija: POS search, Arhiva opisivanje, Journal description, Smart Import instrukcije.

## Tehnologija
- Web Speech API (SpeechRecognition / webkitSpeechRecognition)
- Browser support: Chrome 100+, Edge 100+, Safari 14.1+
- Firefox: NIJE podržan (koristi fallback UI)
- Jezik: HR, DE, EN (prema UserProfile.language)
- NO server dependency — sve se procesira u browseru (Google servers za Chrome)

## fenix-voice.js (iz PLAN_007C)
```javascript
/**
 * FenixVoice — Web Speech API wrapper
 * Koristi se kao Alpine.js plugin ili standalone
 */
class FenixVoice {
  constructor(options = {}) {
    this.lang = options.lang || document.documentElement.lang || 'hr-HR';
    this.continuous = options.continuous || false;
    this.interimResults = options.interimResults || true;
    this.onResult = options.onResult || (() => {});
    this.onError = options.onError || (() => {});
    this.onStart = options.onStart || (() => {});
    this.onEnd = options.onEnd || (() => {});
    this.recognition = null;
    this.isListening = false;
    this.isSupported = 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window;
  }

  init() {
    if (!this.isSupported) return false;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SR();
    this.recognition.lang = this._mapLang(this.lang);
    this.recognition.continuous = this.continuous;
    this.recognition.interimResults = this.interimResults;
    this.recognition.maxAlternatives = 1;

    this.recognition.onstart = () => {
      this.isListening = true;
      this.onStart();
    };
    this.recognition.onend = () => {
      this.isListening = false;
      this.onEnd();
    };
    this.recognition.onerror = (event) => {
      this.isListening = false;
      this.onError(event.error);
    };
    this.recognition.onresult = (event) => {
      const last = event.results[event.results.length - 1];
      const transcript = last[0].transcript;
      const isFinal = last.isFinal;
      this.onResult(transcript, isFinal);
    };
    return true;
  }

  start() {
    if (!this.recognition) this.init();
    if (!this.isListening) {
      try {
        this.recognition.start();
      } catch (e) {
        // Already started
      }
    }
  }

  stop() {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
    }
  }

  toggle() {
    this.isListening ? this.stop() : this.start();
  }

  _mapLang(lang) {
    const map = {
      'hr': 'hr-HR',
      'de': 'de-DE',
      'en': 'en-US',
      'hr-HR': 'hr-HR',
      'de-DE': 'de-DE',
      'en-US': 'en-US',
    };
    return map[lang] || 'hr-HR';
  }
}

window.FenixVoice = FenixVoice;
```

## Alpine.js plugin: voiceInput()
```javascript
/**
 * Alpine.js data function za input polje s glasovnim unosom.
 * Koristi se: x-data="voiceInput({target: 'description', lang: 'hr'})"
 */
function voiceInput(options = {}) {
  return {
    isListening: false,
    isSupported: false,
    transcript: '',
    error: null,
    voice: null,

    init() {
      this.voice = new FenixVoice({
        lang: options.lang || Alpine.store('fenix').user?.language || 'hr',
        continuous: false,
        interimResults: true,
        onStart: () => { this.isListening = true; this.error = null; },
        onEnd: () => { this.isListening = false; },
        onError: (err) => {
          this.isListening = false;
          if (err === 'not-allowed') {
            this.error = 'Mikrofon nije odobren. Dozvoli pristup mikrofonu u preglednicku.';
          } else if (err === 'no-speech') {
            this.error = 'Nije detektiran govor. Pokušaj ponovo.';
          } else {
            this.error = `Greška: ${err}`;
          }
        },
        onResult: (text, isFinal) => {
          this.transcript = text;
          if (isFinal && options.target) {
            // Inject into target Alpine store or element
            const el = this.$root.querySelector(`[data-voice-target="${options.target}"]`);
            if (el) {
              // Trigger Alpine model update
              el.value = text;
              el.dispatchEvent(new Event('input'));
            }
            if (options.onFinal) options.onFinal(text);
          }
        },
      });
      this.isSupported = this.voice.init();
    },

    toggle() { this.voice?.toggle(); },
    start() { this.voice?.start(); },
    stop() { this.voice?.stop(); },
  };
}
```

## UI Komponenta: Voice Button
HTML component koji se ubacuje uz svako input polje koje podržava glasovni unos:

```html
<!-- Koristi se u templateima ovako: -->
<!-- {% include "components/voice_input_btn.html" with target="description" %} -->

<!-- components/voice_input_btn.html -->
<div x-data="voiceInput({ target: '{{ target }}' })" class="inline-flex items-center">
  <!-- Gumb vidljiv samo ako browser podržava -->
  <button
    x-show="isSupported"
    @click="toggle()"
    type="button"
    :class="isListening
      ? 'bg-red-100 text-red-600 border-red-300 animate-pulse'
      : 'bg-gray-100 text-gray-500 border-gray-300 hover:bg-fenix-50 hover:text-fenix-600'"
    class="ml-2 p-2 rounded-lg border transition-colors"
    :title="isListening ? 'Zaustavi snimanje' : 'Glasovni unos'"
    :aria-label="isListening ? 'Zaustavi glasovni unos' : 'Pokreni glasovni unos'"
    :aria-pressed="isListening"
  >
    <!-- Mic icon -->
    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4zm0 2a2 2 0 00-2 2v6a2 2 0 004 0V5a2 2 0 00-2-2zM8.5 17.5A5.5 5.5 0 0017.5 12H19a7 7 0 01-6 6.93V21h-2v-2.07A7 7 0 015 12h1.5a5.5 5.5 0 003 5.5z"/>
    </svg>
  </button>

  <!-- Interim transcript prikaz -->
  <span x-show="isListening && transcript"
        class="ml-2 text-sm text-gray-500 italic animate-pulse"
        x-text="'🎤 ' + transcript">
  </span>

  <!-- Error -->
  <span x-show="error" class="ml-2 text-sm text-red-500" x-text="error"></span>
</div>
```

## Integracije

### 1. POS Search (PLAN_048)
```html
<!-- pos/terminal.html — product search field -->
<div class="flex items-center gap-2">
  <input type="search"
    x-model="searchQuery"
    @input.debounce.300="searchProducts()"
    data-voice-target="pos_search"
    class="input flex-1"
    placeholder="Pretraži proizvode..."
    id="pos-search">
  
  {% include "components/voice_input_btn.html" with target="pos_search" %}
</div>
```

Alpine.js u POS:
```javascript
// U posTerminal() x-data:
// voice unos → searchQuery se mijenja → searchProducts() se triggera
```

### 2. Arhiva — opis dokumenta (PLAN_026)
```html
<!-- arhiva/upload.html -->
<label class="label">Opis dokumenta</label>
<div class="flex items-start gap-2">
  <textarea x-model="description"
    data-voice-target="description"
    class="input flex-1 h-20"
    placeholder="npr. Račun za uredski materijal od dobaljavca...">
  </textarea>
  {% include "components/voice_input_btn.html" with target="description" %}
</div>
```

### 3. Journal Entry — opis knjiženja (PLAN_042)
```html
<div class="flex items-center gap-2">
  <input type="text"
    x-model="description"
    data-voice-target="journal_description"
    class="input flex-1"
    placeholder="Opis knjiženja">
  {% include "components/voice_input_btn.html" with target="journal_description" %}
</div>
```

### 4. Smart Import — instrukcije (PLAN_053)
```html
<!-- Korisnik može glasom reći: "Ovo su fakture od Simens za travanj" -->
<div class="flex items-center gap-2">
  <input type="text"
    x-model="batchNote"
    data-voice-target="batch_note"
    class="input flex-1"
    placeholder="Napomena za ovaj batch (opcija)">
  {% include "components/voice_input_btn.html" with target="batch_note" %}
</div>
```

### 5. AI Cockpit — upit (PLAN_052)
```html
<div class="flex items-center gap-2">
  <input type="text"
    x-model="question"
    data-voice-target="ai_question"
    class="input flex-1"
    placeholder="Postavi pitanje AI-u...">
  {% include "components/voice_input_btn.html" with target="ai_question" %}
</div>
```

## Django template tag
```python
# templatetags/voice_tags.py
from django import template
register = template.Library()

@register.inclusion_tag("components/voice_input_btn.html", takes_context=True)
def voice_btn(context, target, lang=None):
    user = context.get("request", None) and context["request"].user
    user_lang = lang
    if not user_lang and user and hasattr(user, "profile"):
        user_lang = user.profile.language
    return {"target": target, "lang": user_lang or "hr"}
```

Upotreba u templateima:
```html
{% load voice_tags %}
{% voice_btn "description" %}
{% voice_btn "description" lang="de" %}
```

## Accessibility zahtjevi (iz PLAN_007C)
- Gumb mora imati `aria-label` koji se mijenja (Pokreni/Zaustavi)
- `aria-pressed` state za screen readere
- Vizualni feedback: crvena boja + animate-pulse dok snima
- Error poruka čitljiva screen readerom (`role="alert"`)
- Tipkovnički shortcut: Alt+M za toggle mikrofona (globalno)

```javascript
// fenix.js — globalni keyboard shortcut
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.key === 'm') {
    e.preventDefault();
    // Trigger voice toggle na focused elementu ili zadnjem aktivnom
    const activeVoiceBtn = document.querySelector('[aria-label*="glasovni"], [aria-label*="Glasovni"]');
    if (activeVoiceBtn) activeVoiceBtn.click();
  }
});
```

## Fallback za Firefox
```javascript
// U voiceInput.init():
if (!this.isSupported) {
  // Firefox korisnici dobijaju tooltip
  this.$el.querySelector('[x-show="isSupported"]')?.setAttribute('title',
    'Glasovni unos nije podržan u Firefox. Koristi Chrome ili Edge.'
  );
}
```

## Jezici — HR posebnosti
Web Speech API za hr-HR prepoznaje:
- Brojeve: "pet tisuća" → 5000 (ali je nepouzdano) → korisnik ručno potvrdi
- Datume: "petnaestog travnja" → nije auto-konverzija
- PREPORUKA: Voice unos = drafting text, korisnik pregledava i potvrđuje

## Testovi
```python
# Nema backend testova za Web Speech (browser API)
# E2E testovi s Playwright:
def test_voice_btn_visible_in_chrome(page):
    page.goto("/hr/arhiva/upload/")
    assert page.locator('[aria-label*="Glasovni"]').is_visible()

def test_voice_btn_not_visible_in_firefox(page):
    # Playwright default browser = Chromium, za Firefox potreban poseban config
    ...
```

## Scope limitacije
- NEMA server-side speech-to-text (Google Cloud Speech, Whisper, itd.)
- NEMA snimanje i slanje audio fajla
- Sve je client-side → 0 trošak, 0 GDPR problem s audiom
- Ograničenje: Chrome-only pouzdanost, Safari djelimičan, Firefox bez podrške
