# CC_TASK — SLOVARICA FIX (memio.world)
> Pronašao: Ivan Brtan (pedagoška inspekcija) | Zapisao: Sonnet 2026-04-18
> Propust pedagoga: standardna štampana slova + provjera točnosti unosa

---

## PROPUST 1 — FONT: NIJE STANDARDNI ŠTAMPANI OBLIK

**Problem:**
Slovarica koristi `Uncial Antiqua` i `MedievalSharp` font — to su kaligrafski/
medievalni fontovi. Djeca u 1. razredu uče STANDARDNA ŠTAMPANA slova 
(Latin Modern, ili clean sans-serif). Medijevalni font za Đ, Š, Ž, Ć, Č 
izgleda drugačije od onoga što dijete vidi u udžbeniku.

**Kritično za:** Đ, Š, Ž, Ć, Č, NJ, LJ, DŽ — hrvatska specifičnost.

**Fix:**
```css
/* Zamijeniti u alphabet_game.html */

/* STARO — neispravno za učenje */
.ld-letter { font-family: 'Uncial Antiqua', serif; }
.letter-btn { font-family: 'Uncial Antiqua', serif; }

/* NOVO — standardni štampani oblik */
/* Opcija A: Google Fonts — Andika (dizajniran za djecu koja uče čitati) */
@import url('https://fonts.googleapis.com/css2?family=Andika&display=swap');
.ld-letter { 
    font-family: 'Andika', 'Comic Sans MS', sans-serif; 
    font-size: 8rem; 
}
.letter-btn { 
    font-family: 'Andika', 'Comic Sans MS', sans-serif; 
}

/* Opcija B: OpenDyslexic (pristupačnost + čitljivost) */
/* Opcija C: System sans-serif za maksimalnu čitljivost */
.ld-letter { font-family: Arial, Helvetica, sans-serif; font-weight: bold; }
```

**Preporuka:** Andika font (dizajniran specifično za početno opismenjavanje).

---

## PROPUST 2 — CANVAS: NEMA PROVJERE TOČNOSTI

**Problem:**
Dijete nacrta slovo na canvasu. Ništa se ne dogodi. Nema:
- Provjere je li nacrtano ispravno
- Ohrabrenja ("Odlično! Baš si dobro nacrtao Š!")
- Zvučnog feedbacka
- Ponavljanja ako nije točno

**Fix — JS provjera + ohrabrenje:**

```javascript
// Dodati u alphabet_game.html <script> sekciju

// ── Ohrabrenja po slovu (prilagođena HR dijakritikama) ──────────────
var ENCOURAGEMENTS = {
    'Š': ["Super! Šešir ima tri crtice — baš kao tvoje Š!", "Bravo! Š je kao S s kapom!", "Izvrsno!"],
    'Ž': ["Živio! Žaba bi bila ponosna na tvoje Ž!", "Odlično! Ž je kao Z s kapom!"],
    'Đ': ["Divno! Đak si prvak!", "Bravo! Đ je jedino slovo s prečkom!"],
    'Č': ["Čudesno! Čokolada čeka!", "Bravo! Č je kao C s kapom!"],
    'Ć': ["Ćao šampione! Ćup je pun medvjeđa!", "Odlično!"],
    'NJ': ["Njami! Baš si vješt s NJ!", "Njuška bi te osjetila — odlično!"],
    'LJ': ["Ljubazno nacrtan!", "Ljuljačka bi rekla: super!"],
    'DŽ': ["Džepno remek-djelo!", "Odlično! DŽ je složeno slovo!"],
    'default': ["Bravo!", "Odlično!", "Super si!", "Nastavi ovako!", "Prvak si!"]
};

// ── Provjera pisanja (pixel density metoda) ──────────────────────────
function checkWriting() {
    var canvas = document.getElementById('writeCanvas');
    var ctx = canvas.getContext('2d');
    var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    var pixels = imageData.data;
    
    // Broji tamne piksele (dijete je pisalo)
    var darkPixels = 0;
    for (var i = 0; i < pixels.length; i += 4) {
        var brightness = (pixels[i] + pixels[i+1] + pixels[i+2]) / 3;
        if (brightness < 100) darkPixels++;
    }
    
    var coverage = darkPixels / (canvas.width * canvas.height);
    
    if (coverage < 0.005) {
        // Gotovo ništa nacrtano
        return null;
    } else if (coverage < 0.02) {
        return 'partial'; // Malo nacrtano
    } else {
        return 'good'; // Dovoljno nacrtano
    }
}

function onCanvasStopDrawing() {
    // Pozvati 1s nakon što dijete prestane crtati
    clearTimeout(window._checkTimer);
    window._checkTimer = setTimeout(function() {
        var result = checkWriting();
        if (result === 'good') {
            showEncouragement();
        } else if (result === 'partial') {
            speakEncouragement("Idi dalje — nacrta cijelo slovo!");
        }
    }, 1000);
}

function showEncouragement() {
    var item = ALPHABET[currentIdx];
    if (!item) return;
    
    var msgs = ENCOURAGEMENTS[item.letter] || ENCOURAGEMENTS['default'];
    var msg = msgs[Math.floor(Math.random() * msgs.length)];
    
    // Vizualno
    var el = document.getElementById('encouragementMsg');
    if (!el) {
        el = document.createElement('div');
        el.id = 'encouragementMsg';
        el.style.cssText = 'text-align:center;font-size:1.3rem;color:#1D9E75;' +
            'font-weight:bold;margin-top:0.5rem;animation:fadeUp 0.4s ease-out;';
        document.querySelector('.write-area').appendChild(el);
    }
    el.textContent = '⭐ ' + msg;
    el.style.display = 'block';
    
    // Zvučno
    speakEncouragement(msg);
    
    // Sakrij nakon 3s
    setTimeout(function() { el.style.display = 'none'; }, 3000);
}

function speakEncouragement(text) {
    var u = new SpeechSynthesisUtterance(text);
    u.lang = 'hr-HR';
    u.rate = 0.9;
    u.pitch = 1.2; // Viši ton = veseliji
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
}

// ── Dodati na canvas event listenere ────────────────────────────────
// (U postojeće mouseup i touchend handlere dodati poziv)
canvas.addEventListener('mouseup', function() { 
    drawing = false; 
    onCanvasStopDrawing(); // DODATI
});
canvas.addEventListener('touchend', function() { 
    drawing = false; 
    onCanvasStopDrawing(); // DODATI
});
```

---

## PROPUST 3 — GLASOVI ZA DIJAKRITIKE (snimiti)

**Problem:**
`SpeechSynthesis` API za `hr-HR` nije dostupan na svim uređajima.
Posebno NJ, LJ, DŽ — složena slova — TTS ih često čita pogrešno.

**Fix — snimiti audio za svako slovo:**

```
Datoteke koje treba snimiti (hr-HR, ženski ili dječji glas):
/static/memio_world/audio/letters/
  a.mp3, b.mp3, c.mp3, č.mp3, ć.mp3, d.mp3, đ.mp3, dž.mp3,
  e.mp3, f.mp3, g.mp3, h.mp3, i.mp3, j.mp3, k.mp3, l.mp3,
  lj.mp3, m.mp3, n.mp3, nj.mp3, o.mp3, p.mp3, r.mp3, s.mp3,
  š.mp3, t.mp3, u.mp3, v.mp3, z.mp3, ž.mp3
```

**JS fallback logika:**
```javascript
function speakLetter() {
    var item = ALPHABET[currentIdx];
    if (!item) return;
    
    // Pokušaj s audio datotekom (preloaded)
    var audioKey = item.letter.toLowerCase()
        .replace('lj','lj').replace('nj','nj').replace('dž','dž');
    var audio = new Audio('/static/memio_world/audio/letters/' + audioKey + '.mp3');
    
    audio.onerror = function() {
        // Fallback na TTS ako nema audio datoteke
        var u = new SpeechSynthesisUtterance(item.letter);
        u.lang = 'hr-HR'; u.rate = 0.7; u.pitch = 1.1;
        speechSynthesis.cancel();
        speechSynthesis.speak(u);
    };
    audio.play().catch(function() {
        // Fallback
        var u = new SpeechSynthesisUtterance(item.letter);
        u.lang = 'hr-HR'; u.rate = 0.7; u.pitch = 1.1;
        speechSynthesis.speak(u);
    });
}
```

**Kako snimiti glasove:**
Opcija A: Web Speech API snimač (besplatno, Ivan snimi na mobitelu)
Opcija B: ElevenLabs API (visoka kvaliteta, ~$5 za 30 audio fajlova)
Opcija C: Google TTS API (dobra kvaliteta, hr-HR podržan)

Preporuka: ElevenLabs jednom → trajno u /static/.

---

## PEDAGOŠKA NAPOMENA (za Java rekreaciju)

> Zapisano po nalogu Ivana Brtana 2026-04-18 — koristiti kao osnovu za novi kod.

Magistar pedagogije primijetio je da:
1. Font mora biti standardni štampani (Andika ili clean sans-serif) — ne kaligrafski
2. Složena slova (NJ, LJ, DŽ) trebaju poseban tretman — veći prikaz, sporiji izgovor
3. Canvas unos mora imati provjeru i ohrabrenje — djetetu treba feedback
4. Glasovni feedback mora biti na hr-HR — TTS fallback nije dovoljan za dijakritike
5. Redoslijed slova: abecedni (A, B, C, Č, Ć, D, Đ, DŽ...) — trenutni je ispravan
6. Posebna sekcija za "složena slova" (NJ, LJ, DŽ) — djeca ih uče odvojeno

**Ove korekture vrijede za SVE buduće verzije** (Django, Java, ili bilo koji stack).
Commit koji ovo bilježi: koristiti kao pedagoški spec dokument.

