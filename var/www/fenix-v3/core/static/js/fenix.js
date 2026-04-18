/**
 * Fenix v3 — JavaScript Engine | 13/10
 *
 * Tri iz budućnosti na SVAKOM ekranu:
 * 1. AI Oblačić — tihi asistent, max 2 rečenice, zvučnik za čitanje
 * 2. Glasovni unos — Web Speech API, HR + DE + EN
 * 3. Prediktivni unos — AI predlaže sljedeći korak
 *
 * Zero dependencies. Vanilla JS. Progressive enhancement.
 * Ako browser ne podržava Speech API — form i dalje radi.
 */

"use strict";

const Fenix = {
  // ═══════════════════════════════════════════
  // INIT
  // ═══════════════════════════════════════════
  init() {
    this.AI.init();
    this.Voice.init();
    this.Accessibility.init();
    this.HTMX.init();
    console.log("[Fenix] Engine started — 13/10 mode");
  },

  // ═══════════════════════════════════════════
  // AI OBLAČIĆ
  // ═══════════════════════════════════════════
  AI: {
    bubble: null,
    enabled: true,
    queue: [],
    speaking: false,

    init() {
      this.enabled = localStorage.getItem("fenix-ai-enabled") !== "false";
      this._createBubbleDOM();
      this._loadPageHint();
    },

    _createBubbleDOM() {
      // Toggle button (always visible)
      const toggle = document.createElement("button");
      toggle.className = "fenix-ai-toggle";
      toggle.id = "fenix-ai-toggle";
      toggle.setAttribute("aria-label", "AI asistent");
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
      toggle.addEventListener("click", () => this.toggle());

      // Bubble container
      const bubble = document.createElement("div");
      bubble.className = "fenix-ai-bubble";
      bubble.id = "fenix-ai-bubble";
      bubble.setAttribute("role", "complementary");
      bubble.setAttribute("aria-label", "AI asistent");
      bubble.hidden = true;
      bubble.innerHTML = `
        <div class="fenix-ai-bubble-content">
          <div class="fenix-ai-bubble-text" id="fenix-ai-text" aria-live="polite"></div>
          <button class="fenix-ai-speak-btn" id="fenix-ai-speak"
                  aria-label="Pročitaj naglas"
                  title="Pročitaj naglas">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
            </svg>
          </button>
          <button class="fenix-btn-ghost" id="fenix-ai-close"
                  aria-label="Zatvori AI poruku"
                  style="min-width:36px;min-height:36px;padding:4px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      `;

      document.body.appendChild(toggle);
      document.body.appendChild(bubble);

      document.getElementById("fenix-ai-speak").addEventListener("click", () => this.speak());
      document.getElementById("fenix-ai-close").addEventListener("click", () => this.hide());

      this.bubble = bubble;
    },

    _loadPageHint() {
      const hint = document.querySelector("[data-ai-hint]");
      if (hint && hint.dataset.aiHint) {
        setTimeout(() => this.show(hint.dataset.aiHint), 1500);
      }
    },

    show(message) {
      if (!this.enabled || !message) return;
      const text = document.getElementById("fenix-ai-text");
      if (text) {
        text.textContent = message;
        this.bubble.hidden = false;
        document.getElementById("fenix-ai-toggle").setAttribute("aria-expanded", "true");
        document.getElementById("fenix-ai-toggle").style.display = "none";
      }
    },

    hide() {
      if (this.bubble) {
        this.bubble.hidden = true;
        document.getElementById("fenix-ai-toggle").setAttribute("aria-expanded", "false");
        document.getElementById("fenix-ai-toggle").style.display = "";
      }
      this.stopSpeaking();
    },

    toggle() {
      if (this.bubble.hidden) {
        const text = document.getElementById("fenix-ai-text");
        if (text && !text.textContent) {
          text.textContent = "Kako vam mogu pomoći?";
        }
        this.show(text?.textContent);
      } else {
        this.hide();
      }
    },

    speak() {
      if (this.speaking) {
        this.stopSpeaking();
        return;
      }

      const text = document.getElementById("fenix-ai-text")?.textContent;
      if (!text || !("speechSynthesis" in window)) return;

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = document.documentElement.lang || "hr";
      utterance.rate = 0.9;

      const speakBtn = document.getElementById("fenix-ai-speak");
      speakBtn?.classList.add("speaking");
      this.speaking = true;

      utterance.onend = () => {
        speakBtn?.classList.remove("speaking");
        this.speaking = false;
      };

      speechSynthesis.cancel();
      speechSynthesis.speak(utterance);
    },

    stopSpeaking() {
      speechSynthesis?.cancel();
      this.speaking = false;
      document.getElementById("fenix-ai-speak")?.classList.remove("speaking");
    },

    setEnabled(enabled) {
      this.enabled = enabled;
      localStorage.setItem("fenix-ai-enabled", String(enabled));
      if (!enabled) this.hide();
    }
  },

  // ═══════════════════════════════════════════
  // GLASOVNI UNOS — Web Speech API
  // ═══════════════════════════════════════════
  Voice: {
    recognition: null,
    supported: false,
    activeInput: null,
    lang: "hr-HR",

    LANG_MAP: {
      "hr": "hr-HR",
      "de": "de-DE",
      "en": "en-US",
    },

    init() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        console.log("[Fenix.Voice] Speech API not supported — voice buttons hidden");
        document.querySelectorAll(".fenix-voice-btn").forEach(b => b.hidden = true);
        return;
      }

      this.supported = true;
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;

      const htmlLang = document.documentElement.lang || "hr";
      this.lang = this.LANG_MAP[htmlLang] || "hr-HR";
      this.recognition.lang = this.lang;

      this.recognition.onresult = (e) => this._onResult(e);
      this.recognition.onerror = (e) => this._onError(e);
      this.recognition.onend = () => this._onEnd();

      this._attachButtons();
      this._observeNewInputs();
    },

    _attachButtons() {
      document.querySelectorAll(".fenix-voice-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          const targetId = btn.dataset.target;
          const input = targetId ? document.getElementById(targetId) : btn.closest(".fenix-field")?.querySelector("input, textarea");
          if (input) this.start(input, btn);
        });
      });
    },

    _observeNewInputs() {
      // Watch for HTMX-swapped content with new voice buttons
      document.body.addEventListener("htmx:afterSwap", () => {
        this._attachButtons();
      });
    },

    start(inputElement, btn) {
      if (!this.supported) return;

      if (this.activeInput) {
        this.stop();
        return;
      }

      this.activeInput = inputElement;
      btn?.classList.add("listening");
      btn?.setAttribute("aria-label", "Zaustavi snimanje");

      try {
        this.recognition.start();
      } catch (e) {
        this.stop();
      }
    },

    stop() {
      try { this.recognition?.stop(); } catch (e) {}
      this._onEnd();
    },

    _onResult(event) {
      if (!this.activeInput) return;

      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }

      this.activeInput.value = transcript;
      this.activeInput.dispatchEvent(new Event("input", { bubbles: true }));
    },

    _onError(event) {
      console.warn("[Fenix.Voice] Error:", event.error);
      this._onEnd();
    },

    _onEnd() {
      document.querySelectorAll(".fenix-voice-btn.listening").forEach(btn => {
        btn.classList.remove("listening");
        btn.setAttribute("aria-label", "Govori umjesto tipkanja");
      });
      this.activeInput = null;
    },

    setLang(langCode) {
      this.lang = this.LANG_MAP[langCode] || langCode;
      if (this.recognition) this.recognition.lang = this.lang;
    }
  },

  // ═══════════════════════════════════════════
  // PRISTUPAČNOST
  // ═══════════════════════════════════════════
  Accessibility: {
    init() {
      this._ensureSkipLink();
      this._trapFocusInModals();
      this._announcePageChanges();
    },

    _ensureSkipLink() {
      if (document.querySelector(".skip-link")) return;
      const main = document.querySelector("main, [role='main']");
      if (!main) return;
      if (!main.id) main.id = "main-content";

      const skip = document.createElement("a");
      skip.href = `#${main.id}`;
      skip.className = "skip-link";
      skip.textContent = "Preskoči na sadržaj";
      document.body.prepend(skip);
    },

    _trapFocusInModals() {
      document.addEventListener("keydown", (e) => {
        if (e.key !== "Tab") return;
        const modal = document.querySelector("[role='dialog']:not([hidden])");
        if (!modal) return;

        const focusable = modal.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      });
    },

    _announcePageChanges() {
      // HTMX page change → announce to screen readers
      document.body.addEventListener("htmx:afterSettle", (e) => {
        const title = document.querySelector("h1, [data-page-title]");
        if (title) {
          this.announce(title.textContent);
        }
      });
    },

    announce(message) {
      let announcer = document.getElementById("fenix-announcer");
      if (!announcer) {
        announcer = document.createElement("div");
        announcer.id = "fenix-announcer";
        announcer.setAttribute("role", "status");
        announcer.setAttribute("aria-live", "polite");
        announcer.setAttribute("aria-atomic", "true");
        announcer.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);";
        document.body.appendChild(announcer);
      }
      announcer.textContent = "";
      setTimeout(() => { announcer.textContent = message; }, 100);
    }
  },

  // ═══════════════════════════════════════════
  // HTMX ENHANCEMENTS
  // ═══════════════════════════════════════════
  HTMX: {
    init() {
      // Configure HTMX defaults
      if (typeof htmx !== "undefined") {
        htmx.config.defaultSwapStyle = "innerHTML";
        htmx.config.historyCacheSize = 10;
        htmx.config.scrollBehavior = "smooth";
        htmx.config.indicatorClass = "htmx-indicator";

        // Global error handler
        document.body.addEventListener("htmx:responseError", (e) => {
          const status = e.detail.xhr?.status;
          if (status === 403) {
            Fenix.AI.show("Nemate dozvolu za ovu akciju.");
          } else if (status >= 500) {
            Fenix.AI.show("Došlo je do greške. Pokušajte ponovo.");
          }
        });

        // Loading state management
        document.body.addEventListener("htmx:beforeRequest", () => {
          document.body.setAttribute("aria-busy", "true");
        });
        document.body.addEventListener("htmx:afterRequest", () => {
          document.body.removeAttribute("aria-busy");
        });
      }
    }
  },

  // ═══════════════════════════════════════════
  // KEYBOARD SHORTCUTS
  // ═══════════════════════════════════════════
  Keyboard: {
    shortcuts: {},

    register(key, description, callback) {
      this.shortcuts[key] = { description, callback };
    },

    init() {
      document.addEventListener("keydown", (e) => {
        // Don't trigger in input fields
        if (e.target.matches("input, textarea, select, [contenteditable]")) return;

        const key = `${e.ctrlKey ? "ctrl+" : ""}${e.altKey ? "alt+" : ""}${e.key}`;
        const shortcut = this.shortcuts[key];
        if (shortcut) {
          e.preventDefault();
          shortcut.callback();
        }
      });

      // Default shortcuts
      this.register("?", "Prikaži prečice", () => this._showHelp());
      this.register("/", "Fokus na pretragu", () => {
        document.querySelector("[data-search], #search")?.focus();
      });
    },

    _showHelp() {
      const lines = Object.entries(this.shortcuts)
        .map(([key, { description }]) => `${key}: ${description}`)
        .join("\n");
      Fenix.AI.show("Prečice: " + Object.keys(this.shortcuts).join(", "));
    }
  }
};

// Auto-init on DOM ready
document.addEventListener("DOMContentLoaded", () => Fenix.init());
