## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# CC Task — Okrugli stol (AI Tim widget za Ivan Cockpit)

## Što gradimo
Na dnu Ivan Cockpit stranice (`ivan_cockpit.html`) dodaj interaktivni
**Okrugli stol** — SVG krug s 4 sjedišta. Klik na osobu otvara chat formu.

## 4 mjesta za stolom

```
        IVAN
        🧑‍💼
    ╔═══════╗
🤖 ║       ║ 🔵
CC ║  stol  ║ GEMINI
    ╚═══════╝
        🟡
       SONNET
```

| Sjedište | Naziv | Opis | Boja | Kontakt |
|---|---|---|---|---|
| Gore | Ivan | Vlasnik / Enter tipka | #c9a84c (gold) | WhatsApp +385991908089 |
| Lijevo | Claude Code | Izvršava na serveru | #22c55e (green) | Dev API |
| Desno | Gemini | Analiza i kontekst | #3b82f6 (blue) | Context dump |
| Dolje | Sonnet | Koordinator | #f59e0b (amber) | Ovaj chat |

## Implementacija — čisti HTML/CSS/JS u template

Dodaj na kraj `ivan_cockpit.html` PRIJE `</body>`:

```html
<!-- ═══ OKRUGLI STOL ═══ -->
<div style="margin-top:2rem;background:#111;border:1px solid #c9a84c;border-radius:16px;padding:1.5rem;">
  <h3 style="color:#c9a84c;margin:0 0 1rem;font-size:1rem;letter-spacing:2px;text-transform:uppercase;">
    ⬡ Okrugli Stol — Tim
  </h3>

  <!-- SVG stol -->
  <div style="display:flex;justify-content:center;margin-bottom:1.5rem;">
  <svg width="280" height="280" viewBox="0 0 280 280" style="overflow:visible">
    <!-- Stol -->
    <circle cx="140" cy="140" r="60" fill="#1a1a2e" stroke="#c9a84c" stroke-width="2"/>
    <text x="140" y="136" text-anchor="middle" fill="#c9a84c" font-size="11" font-family="monospace">FENIX</text>
    <text x="140" y="150" text-anchor="middle" fill="#666" font-size="9" font-family="monospace">okrugli stol</text>

    <!-- Ivan - gore -->
    <g cursor="pointer" onclick="openChat('ivan')" style="cursor:pointer">
      <circle cx="140" cy="30" r="28" fill="#1a1a2e" stroke="#c9a84c" stroke-width="2" id="seat-ivan"/>
      <text x="140" y="25" text-anchor="middle" font-size="16">🧑‍💼</text>
      <text x="140" y="38" text-anchor="middle" fill="#c9a84c" font-size="9" font-weight="bold">IVAN</text>
      <text x="140" y="48" text-anchor="middle" fill="#888" font-size="7">Vlasnik</text>
    </g>

    <!-- Claude Code - lijevo -->
    <g cursor="pointer" onclick="openChat('cc')" style="cursor:pointer">
      <circle cx="30" cy="140" r="28" fill="#1a1a2e" stroke="#22c55e" stroke-width="2" id="seat-cc"/>
      <text x="30" y="135" text-anchor="middle" font-size="16">🤖</text>
      <text x="30" y="148" text-anchor="middle" fill="#22c55e" font-size="9" font-weight="bold">CC</text>
      <text x="30" y="158" text-anchor="middle" fill="#888" font-size="7">Executor</text>
    </g>

    <!-- Gemini - desno -->
    <g cursor="pointer" onclick="openChat('gemini')" style="cursor:pointer">
      <circle cx="250" cy="140" r="28" fill="#1a1a2e" stroke="#3b82f6" stroke-width="2" id="seat-gemini"/>
      <text x="250" y="135" text-anchor="middle" font-size="16">🔵</text>
      <text x="250" y="148" text-anchor="middle" fill="#3b82f6" font-size="9" font-weight="bold">GEMINI</text>
      <text x="250" y="158" text-anchor="middle" fill="#888" font-size="7">Analyst</text>
    </g>

    <!-- Sonnet - dolje -->
    <g cursor="pointer" onclick="openChat('sonnet')" style="cursor:pointer">
      <circle cx="140" cy="250" r="28" fill="#1a1a2e" stroke="#f59e0b" stroke-width="2" id="seat-sonnet"/>
      <text x="140" y="245" text-anchor="middle" font-size="16">🟡</text>
      <text x="140" y="258" text-anchor="middle" fill="#f59e0b" font-size="9" font-weight="bold">SONNET</text>
      <text x="140" y="268" text-anchor="middle" fill="#888" font-size="7">Koordinator</text>
    </g>

    <!-- Linije od stola do sjedišta -->
    <line x1="140" y1="80" x2="140" y2="58" stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>
    <line x1="80" y1="140" x2="58" y2="140" stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>
    <line x1="200" y1="140" x2="222" y2="140" stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>
    <line x1="140" y1="200" x2="140" y2="222" stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>
  </svg>
  </div>

  <!-- Chat panel — otvori se kad klikneš -->
  <div id="table-chat" style="display:none;background:#0d1117;border:1px solid #333;border-radius:10px;padding:1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem">
      <span id="chat-title" style="color:#c9a84c;font-weight:700;font-size:.9rem"></span>
      <button onclick="closeChat()"
              style="background:none;border:none;color:#888;font-size:1.2rem;cursor:pointer">✕</button>
    </div>
    <div id="chat-desc" style="font-size:.75rem;color:#64748b;margin-bottom:.75rem"></div>

    <!-- Forma za poruku -->
    <div id="chat-form-area">
      <textarea id="chat-msg" rows="3"
                placeholder="Upiši poruku ili zadatak..."
                style="width:100%;background:#111;color:#fff;border:1px solid #444;
                       border-radius:6px;padding:.5rem;font-size:.8rem;
                       resize:vertical;font-family:inherit"></textarea>
      <div style="display:flex;gap:.5rem;margin-top:.5rem">
        <button id="chat-send-btn" onclick="sendToAgent()"
                style="background:#c9a84c;color:#000;border:none;border-radius:6px;
                       padding:.4rem 1rem;font-weight:700;cursor:pointer;font-size:.8rem">
          Pošalji
        </button>
        <div id="chat-status" style="font-size:.75rem;color:#888;padding:.4rem 0"></div>
      </div>
    </div>

    <!-- Response area -->
    <div id="chat-response" style="display:none;margin-top:.75rem;background:#111;
         border-left:3px solid #c9a84c;padding:.75rem;border-radius:0 6px 6px 0;
         font-size:.8rem;color:#ccc;white-space:pre-wrap;max-height:200px;overflow-y:auto"></div>
  </div>
</div>

<script>
const AGENTS = {
  ivan: {
    name: '🧑‍💼 Ivan Brtan',
    desc: 'Vlasnik projekta — Enter tipka. WhatsApp ili direktna poruka.',
    color: '#c9a84c',
    type: 'whatsapp',
    phone: '+385991908089'
  },
  cc: {
    name: '🤖 Claude Code',
    desc: 'Izvršava zadatke direktno na serveru. Piše kod, testira, deploya.',
    color: '#22c55e',
    type: 'task',
    endpoint: '/superadmin/ai/api/submit-request/'
  },
  gemini: {
    name: '🔵 Gemini',
    desc: 'Analiza arhitekture, kontekst dump, EU/legal pregled. Daj mu context, vrati analizu.',
    color: '#3b82f6',
    type: 'context',
    file: 'GEMINI_TASK_'
  },
  sonnet: {
    name: '🟡 Claude Sonnet',
    desc: 'Koordinator tima. Planiranje, pečat, finalna potvrda. claude.ai chat.',
    color: '#f59e0b',
    type: 'claude',
    url: 'https://claude.ai'
  }
};

let currentAgent = null;

function openChat(agent) {
  currentAgent = agent;
  const a = AGENTS[agent];
  document.getElementById('table-chat').style.display = 'block';
  document.getElementById('chat-title').textContent = a.name;
  document.getElementById('chat-title').style.color = a.color;
  document.getElementById('chat-desc').textContent = a.desc;
  document.getElementById('chat-response').style.display = 'none';
  document.getElementById('chat-msg').value = '';
  document.getElementById('chat-status').textContent = '';

  // Highlight sjedište
  Object.keys(AGENTS).forEach(k => {
    const el = document.getElementById('seat-' + k);
    if (el) el.style.filter = k === agent ? 'brightness(1.5)' : 'brightness(0.6)';
  });

  document.getElementById('table-chat').scrollIntoView({behavior:'smooth', block:'nearest'});
}

function closeChat() {
  document.getElementById('table-chat').style.display = 'none';
  Object.keys(AGENTS).forEach(k => {
    const el = document.getElementById('seat-' + k);
    if (el) el.style.filter = '';
  });
}

function sendToAgent() {
  const msg = document.getElementById('chat-msg').value.trim();
  if (!msg) return;
  const a = AGENTS[currentAgent];
  const status = document.getElementById('chat-status');

  if (a.type === 'whatsapp') {
    // Šalje WhatsApp Ivanu
    status.textContent = 'Šaljem na WhatsApp...';
    fetch('/superadmin/ai/api/submit-request/', {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
      body: JSON.stringify({
        description: '[COCKPIT → IVAN] ' + msg,
        module: 'cockpit',
        priority: 1
      })
    }).then(() => {
      // Također pokušaj WhatsApp
      fetch('/api/whatsapp-send/', {
        method: 'POST',
        headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
        body: JSON.stringify({phone: a.phone, message: '🔥 Cockpit poruka:\n\n' + msg})
      }).catch(() => {});
      status.textContent = '✅ Zabilježeno';
    });

  } else if (a.type === 'task') {
    // Claude Code — submit task
    status.textContent = 'Šaljem CC agentu...';
    fetch(a.endpoint, {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
      body: JSON.stringify({description: msg, module: 'cockpit', priority: 2})
    }).then(r => r.json()).then(d => {
      status.textContent = d.ok || d.id ? '✅ Task kreiran' : '⚠️ ' + (d.error || 'greška');
    }).catch(() => { status.textContent = '❌ Nije dosegnut'; });

  } else if (a.type === 'context') {
    // Gemini — spremi kao context file
    status.textContent = 'Kreiram Gemini context...';
    fetch('/superadmin/ai/api/submit-request/', {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
      body: JSON.stringify({
        description: '[GEMINI CONTEXT]\n\n' + msg,
        module: 'cockpit',
        priority: 2
      })
    }).then(() => {
      status.textContent = '✅ Spremljeno — kopiraj Geminu';
      const resp = document.getElementById('chat-response');
      resp.style.display = 'block';
      resp.textContent = '📋 Context za Gemini:\n\n' + msg + '\n\n→ Kopiraj i paste u Gemini razgovor';
    });

  } else if (a.type === 'claude') {
    // Sonnet — otvori claude.ai
    status.textContent = '→ Otvaram claude.ai...';
    const resp = document.getElementById('chat-response');
    resp.style.display = 'block';
    resp.textContent = '💬 Poruka za Soneta:\n\n' + msg + '\n\n→ Kopiraj ovo i paste u claude.ai';
    setTimeout(() => window.open(a.url, '_blank'), 800);
  }
}

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}
</script>
```

## PRAVILA
- Ne diraj ništa drugo u ivan_cockpit.html osim dodavanja ovog bloka
- SVG mora biti responsive (max-width:280px, margin:auto)
- CSRF token uzimaj iz cookie, ne iz template taga
- Svaki agent ima drugačiju logiku slanja — pročitaj type polje
- Django check mora biti 0 issues nakon
