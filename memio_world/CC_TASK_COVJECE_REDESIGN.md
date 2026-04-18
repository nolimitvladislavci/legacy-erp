# CC_TASK — ČOVJEČE NE LJUTI SE: KOMPLETNI REDESIGN
> Vizija: Ivan Brtan 2026-04-18 | Spec: Sonnet | Za: CC Code
> Stara igrica: canvas s kružnom stazom, figure ne reagiraju na klik
> Nova igrica: pravolinijska staza, tvrđave, 2-4 igrača, online/offline

---

## NOVA VIZIJA (Ivan Brtan spec)

```
TVRĐAVA A ←←←←←←←←← STAZA →→→→→→→→→→ TVRĐAVA B
[🏰🔴🔴]  [ ][ ][ ][ ][ ][ ][ ][ ]  [🏰🔵🔵]
           ← 3 duljine po izboru →
```

**Ključne odluke dizajna:**
- Pravolinijska staza (ne klasična kružna Ludo ploča)
- Igrači kreću s OBJE strane prema sredini/cilju
- Svaki igrač ima tvrđavu (vizualni home) na svojoj strani
- Dvije figure po igraču (ne četiri — jednostavnije za djecu)
- Tri duljine staze: Kratka (10 polja), Srednja (20), Duga (30)
- Iste boje tvrđava = isti cilj → susreću se negdje na stazi
- Sve uvećano — polja 80x80px, figure 60px
- Online (2-4 igrača) i Offline (2-4 igrača na istom uređaju)

---

## ARHITEKTURA

### Offline verzija (implementirati prvo)
Isti uređaj, izmjenični potezi, 2-4 igrača.
Svaki igrač tapne "Baci kocku" za sebe.

### Online verzija (Django Channels WebSocket)
Svaki igrač na svom uređaju. Room kod za spajanje.
WebSocket event: `{type: "move", player: 1, piece: 0, from: 5, to: 8}`

---

## IMPLEMENTACIJA

### FILE: templates/memio_world/ludo_game.html (ZAMJENA)

```html
<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎲 Čovječe ne ljuti se — MEMIO</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { 
  background: #f5e6c8; 
  font-family: 'Segoe UI', sans-serif;
  min-height: 100vh;
  display: flex; flex-direction: column; align-items: center;
  padding: 1rem;
}

/* ── SETUP EKRAN ──────────────────────────────────────── */
#setupScreen {
  background: #fff;
  border-radius: 20px;
  padding: 2rem;
  max-width: 400px;
  width: 100%;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  text-align: center;
}
#setupScreen h1 { font-size: 2rem; color: #2c1810; margin-bottom: 1rem; }
.setup-option { margin: 1rem 0; }
.setup-label { font-size: 0.9rem; color: #6b5a4e; margin-bottom: 0.5rem; }
.btn-group { display: flex; gap: 0.5rem; justify-content: center; }
.btn-select {
  padding: 0.6rem 1.2rem; border: 2px solid #c9a84c; background: #fff;
  border-radius: 10px; cursor: pointer; font-size: 1rem; transition: 0.2s;
}
.btn-select.active { background: #c9a84c; color: #fff; }
.btn-start {
  width: 100%; padding: 1rem; background: #c9a84c; color: #fff;
  border: none; border-radius: 12px; font-size: 1.2rem; cursor: pointer;
  margin-top: 1rem; font-weight: bold;
}

/* ── GAME SCREEN ──────────────────────────────────────── */
#gameScreen { display: none; width: 100%; max-width: 900px; }

.game-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.5rem 1rem; background: #fff; border-radius: 12px;
  margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.turn-badge {
  padding: 0.4rem 1rem; border-radius: 20px; color: #fff;
  font-weight: bold; font-size: 1rem;
}

/* ── STAZA ───────────────────────────────────────────── */
.race-container {
  display: flex; align-items: center; gap: 1rem;
  overflow-x: auto; padding: 1rem 0;
}

.fortress {
  min-width: 120px; height: 120px;
  border-radius: 16px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 0.5rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  flex-shrink: 0;
}
.fortress-icon { font-size: 2.5rem; }
.fortress-pieces { display: flex; gap: 4px; }

.track {
  display: flex; gap: 6px; align-items: center;
  flex-wrap: nowrap;
}
.cell {
  width: 72px; height: 72px;
  background: #fff; border: 3px solid #ddd;
  border-radius: 12px; position: relative;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: 0.2s;
}
.cell.start-a { border-color: var(--color-a, #e53935); background: rgba(229,57,53,0.1); }
.cell.start-b { border-color: var(--color-b, #1e88e5); background: rgba(30,136,229,0.1); }
.cell.goal { 
  background: linear-gradient(135deg, #c9a84c, #8b6914);
  border-color: #8b6914; border-width: 4px;
  box-shadow: 0 0 20px rgba(201,168,76,0.5);
}
.cell.highlight {
  border-color: #c9a84c !important;
  box-shadow: 0 0 0 4px rgba(201,168,76,0.4);
  cursor: pointer;
  animation: pulse-cell 0.8s infinite alternate;
}
@keyframes pulse-cell {
  from { box-shadow: 0 0 0 2px rgba(201,168,76,0.3); }
  to   { box-shadow: 0 0 0 6px rgba(201,168,76,0.5); }
}

/* ── FIGURE ──────────────────────────────────────────── */
.piece {
  width: 52px; height: 52px;
  border-radius: 50%; border: 3px solid rgba(0,0,0,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem; cursor: pointer; position: absolute;
  transition: all 0.3s ease;
  box-shadow: 0 3px 10px rgba(0,0,0,0.2);
  user-select: none; -webkit-user-select: none;
}
.piece:hover { transform: scale(1.15); }
.piece.selected { 
  box-shadow: 0 0 0 4px #c9a84c, 0 3px 10px rgba(0,0,0,0.2);
  transform: scale(1.1);
}
/* Dvije figure na istom polju — malo pomak */
.piece-offset-0 { top: 4px; left: 4px; }
.piece-offset-1 { top: 4px; right: 4px; }

/* ── KOCKA ───────────────────────────────────────────── */
.dice-section {
  background: #fff; border-radius: 16px; padding: 1.5rem;
  text-align: center; margin-top: 1rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}
.dice-btn {
  width: 100px; height: 100px; font-size: 3rem;
  background: #fff; border: 3px solid #2c1810;
  border-radius: 20px; cursor: pointer;
  transition: 0.15s; display: inline-flex;
  align-items: center; justify-content: center;
}
.dice-btn:active { transform: scale(0.92); }
.dice-btn.rolling { animation: roll 0.4s; }
@keyframes roll {
  0%,100% { transform: rotate(0deg); }
  25%  { transform: rotate(-15deg) scale(1.1); }
  75%  { transform: rotate(15deg) scale(1.1); }
}
.dice-result { font-size: 2rem; font-weight: bold; color: #2c1810; margin: 0.5rem 0; }
.dice-instruction { color: #6b5a4e; font-size: 0.9rem; min-height: 1.5rem; }

/* ── PORUKE ──────────────────────────────────────────── */
.message-bar {
  padding: 0.8rem 1.2rem; border-radius: 12px;
  text-align: center; font-weight: bold; margin: 0.5rem 0;
  min-height: 2.5rem; transition: 0.3s;
}

/* ── POBJEDNIK ───────────────────────────────────────── */
#winOverlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.7); z-index: 100;
  align-items: center; justify-content: center;
}
#winOverlay.show { display: flex; }
.win-card {
  background: #fff; border-radius: 24px; padding: 3rem 2rem;
  text-align: center; max-width: 320px;
  animation: popIn 0.4s cubic-bezier(0.34,1.56,0.64,1);
}
@keyframes popIn {
  from { transform: scale(0.5); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}
.win-emoji { font-size: 5rem; }
.win-text { font-size: 1.8rem; font-weight: bold; margin: 1rem 0; }
.win-msg { color: #6b5a4e; margin-bottom: 1.5rem; }
.btn-restart {
  padding: 0.8rem 2rem; background: #c9a84c; color: #fff;
  border: none; border-radius: 12px; font-size: 1.1rem;
  cursor: pointer; font-weight: bold;
}
</style>
</head>
<body>

<!-- SETUP -->
<div id="setupScreen">
  <h1>🎲 Čovječe!</h1>
  <p style="color:#6b5a4e;margin-bottom:1.5rem">Trka tvrđava do cilja</p>

  <div class="setup-option">
    <div class="setup-label">Broj igrača</div>
    <div class="btn-group">
      <button class="btn-select active" onclick="setPlayers(2)" id="p2">2 igrača</button>
      <button class="btn-select" onclick="setPlayers(3)" id="p3">3 igrača</button>
      <button class="btn-select" onclick="setPlayers(4)" id="p4">4 igrača</button>
    </div>
  </div>

  <div class="setup-option">
    <div class="setup-label">Duljina staze</div>
    <div class="btn-group">
      <button class="btn-select active" onclick="setLength('short')" id="lShort">Kratka (10)</button>
      <button class="btn-select" onclick="setLength('medium')" id="lMedium">Srednja (20)</button>
      <button class="btn-select" onclick="setLength('long')" id="lLong">Duga (30)</button>
    </div>
  </div>

  <div class="setup-option" id="nameInputs">
    <!-- Dinamički generirani inputi za imena -->
  </div>

  <button class="btn-start" onclick="startGame()">🚀 Kreni!</button>
</div>

<!-- GAME -->
<div id="gameScreen">
  <div class="game-header">
    <span id="turnLabel" class="turn-badge" style="background:#c9a84c">Čekaj...</span>
    <button onclick="restartGame()" style="background:none;border:1px solid #ddd;padding:0.3rem 0.8rem;border-radius:8px;cursor:pointer">↺ Iznova</button>
  </div>

  <div class="message-bar" id="messageBar"></div>

  <!-- Staza se generira JS-om ovdje -->
  <div id="raceWrapper" class="race-container"></div>

  <div class="dice-section">
    <button class="dice-btn" id="diceBtn" onclick="rollDice()">🎲</button>
    <div class="dice-result" id="diceResult">—</div>
    <div class="dice-instruction" id="diceInstruction">Pritisni kocku za bacanje!</div>
  </div>
</div>

<!-- WIN -->
<div id="winOverlay">
  <div class="win-card">
    <div class="win-emoji">🏆</div>
    <div class="win-text" id="winText">Pobijedio!</div>
    <div class="win-msg" id="winMsg"></div>
    <button class="btn-restart" onclick="restartGame()">🔄 Igraj ponovo</button>
  </div>
</div>

<script>
// ── KONFIGURACIJA ────────────────────────────────────────────────
var PLAYER_COLORS = ['#e53935','#1e88e5','#43a047','#fb8c00'];
var PLAYER_LIGHT  = ['#ef9a9a','#90caf9','#a5d6a7','#ffcc80'];
var PLAYER_EMOJIS = ['🔴','🔵','🟢','🟠'];
var FORTRESS_EMOJI = '🏰';
var DICE_FACES = ['','⚀','⚁','⚂','⚃','⚄','⚅'];
var WISDOM = [
  "Gubiti s dostojanstvom je pobjeda karaktera!",
  "Strpljenje je najjača figura u igri.",
  "Svaki korak naprijed, čak i mali, vodi do cilja.",
  "Ponekad trebaš stati da bi drugi prošli — to je mudrost.",
];

// ── STANJE ───────────────────────────────────────────────────────
var config = { players: 2, trackLen: 10, names: ['Crveni','Plavi','Zeleni','Narančasti'] };
var state = {};

// ── SETUP ────────────────────────────────────────────────────────
function setPlayers(n) {
  config.players = n;
  ['p2','p3','p4'].forEach(function(id) {
    document.getElementById(id).classList.remove('active');
  });
  document.getElementById('p'+n).classList.add('active');
  renderNameInputs();
}

function setLength(len) {
  var lens = {short:10, medium:20, long:30};
  config.trackLen = lens[len];
  ['lShort','lMedium','lLong'].forEach(function(id) {
    document.getElementById(id).classList.remove('active');
  });
  document.getElementById('l'+len.charAt(0).toUpperCase()+len.slice(1)).classList.add('active');
}

function renderNameInputs() {
  var html = '';
  for (var i = 0; i < config.players; i++) {
    html += '<div style="display:flex;align-items:center;gap:0.5rem;margin:0.3rem 0">' +
      '<span style="font-size:1.5rem">' + PLAYER_EMOJIS[i] + '</span>' +
      '<input style="flex:1;padding:0.4rem 0.8rem;border:2px solid #ddd;border-radius:8px;font-size:0.9rem" ' +
      'id="name'+i+'" value="' + config.names[i] + '" placeholder="Ime igrača ' + (i+1) + '">' +
      '</div>';
  }
  document.getElementById('nameInputs').innerHTML = html;
}

function startGame() {
  // Dohvati imena
  for (var i = 0; i < config.players; i++) {
    var inp = document.getElementById('name'+i);
    if (inp && inp.value.trim()) config.names[i] = inp.value.trim();
  }
  initState();
  renderGame();
  document.getElementById('setupScreen').style.display = 'none';
  document.getElementById('gameScreen').style.display = 'block';
}

// ── GAME STATE ───────────────────────────────────────────────────
function initState() {
  var n = config.players;
  var tl = config.trackLen;
  
  // Igrači kreću s različitih strana staze
  // 2 igrača: 0 kreće s lijeva (pos=0), 1 kreće s desna (pos=tl-1)
  // 3 igrača: 0 lijevo, 1 desno, 2 lijevo (ali drugom figurom)
  // 4 igrača: 0 i 2 lijevo, 1 i 3 desno
  
  state = {
    turn: 0,
    diceVal: 0,
    diceRolled: false,
    selectedPiece: -1,
    pieces: [],  // [{player, pieceIdx, pos, finished}]
    finished: new Array(n).fill(0), // broj figura u cilju
    winner: -1,
  };
  
  for (var p = 0; p < n; p++) {
    var startFromLeft = (p % 2 === 0);
    for (var pi = 0; pi < 2; pi++) {
      state.pieces.push({
        player: p,
        pieceIdx: pi,
        pos: startFromLeft ? -1 : -(tl + 1), // -1 = home lijevo, -(tl+1) = home desno
        finished: false,
        fromLeft: startFromLeft,
      });
    }
  }
}

// ── RENDERING ───────────────────────────────────────────────────
function renderGame() {
  renderTrack();
  updateUI();
}

function renderTrack() {
  var n = config.players;
  var tl = config.trackLen;
  var wrapper = document.getElementById('raceWrapper');
  wrapper.innerHTML = '';
  
  // Grupe igrača po strani
  var leftPlayers  = [], rightPlayers = [];
  for (var p = 0; p < n; p++) {
    if (p % 2 === 0) leftPlayers.push(p);
    else rightPlayers.push(p);
  }
  
  // ── Lijeve tvrđave ──
  leftPlayers.forEach(function(p) {
    var fort = makeFortress(p);
    wrapper.appendChild(fort);
  });
  
  // ── Staza ──
  var track = document.createElement('div');
  track.className = 'track';
  track.id = 'track';
  
  for (var i = 0; i < tl; i++) {
    var cell = document.createElement('div');
    cell.className = 'cell';
    cell.dataset.pos = i;
    
    // Označi startna polja
    leftPlayers.forEach(function(p) {
      if (i === 0) cell.classList.add('start-a');
    });
    rightPlayers.forEach(function(p) {
      if (i === tl - 1) cell.classList.add('start-b');
    });
    
    // Cilj = sredina staze
    var midL = Math.floor(tl / 2) - 1;
    var midR = Math.floor(tl / 2);
    if (i === midL || i === midR) {
      cell.classList.add('goal');
      cell.title = 'CILJ!';
    }
    
    // Klik na polje = potez ako je figura tu
    cell.addEventListener('click', function(e) { onCellClick(parseInt(this.dataset.pos)); });
    track.appendChild(cell);
  }
  wrapper.appendChild(track);
  
  // ── Desne tvrđave ──
  rightPlayers.forEach(function(p) {
    var fort = makeFortress(p);
    wrapper.appendChild(fort);
  });
  
  placePieces();
}

function makeFortress(p) {
  var fort = document.createElement('div');
  fort.className = 'fortress';
  fort.id = 'fortress-' + p;
  fort.style.background = PLAYER_LIGHT[p];
  fort.style.border = '3px solid ' + PLAYER_COLORS[p];
  fort.innerHTML = '<div class="fortress-icon">' + FORTRESS_EMOJI + '</div>' +
    '<div style="font-weight:bold;color:' + PLAYER_COLORS[p] + '">' + config.names[p] + '</div>' +
    '<div class="fortress-pieces" id="fort-pieces-' + p + '"></div>';
  return fort;
}

function placePieces() {
  // Makni sve figure s ploče
  document.querySelectorAll('.piece').forEach(function(el) { el.remove(); });
  
  // Figure u tvrđavi
  for (var p = 0; p < config.players; p++) {
    var fortEl = document.getElementById('fort-pieces-' + p);
    if (fortEl) fortEl.innerHTML = '';
  }
  
  state.pieces.forEach(function(piece, idx) {
    if (piece.finished) return;
    
    var el = document.createElement('div');
    el.className = 'piece';
    el.dataset.pieceIdx = idx;
    el.style.background = PLAYER_COLORS[piece.player];
    el.textContent = piece.pieceIdx === 0 ? '♟' : '♙';
    el.title = config.names[piece.player] + ' ' + (piece.pieceIdx + 1);
    
    if (piece.pos < 0) {
      // U tvrđavi
      var fortEl = document.getElementById('fort-pieces-' + piece.player);
      if (fortEl) {
        el.style.position = 'relative';
        el.style.width = '44px'; el.style.height = '44px';
        el.style.fontSize = '1.3rem';
        el.addEventListener('click', function() { onPieceClick(parseInt(this.dataset.pieceIdx)); });
        fortEl.appendChild(el);
      }
    } else {
      // Na stazi
      var cellEl = document.querySelector('.cell[data-pos="' + piece.pos + '"]');
      if (cellEl) {
        // Provjeri postoji li već figura na ovom polju
        var existing = cellEl.querySelectorAll('.piece').length;
        el.classList.add('piece-offset-' + existing);
        el.addEventListener('click', function() { onPieceClick(parseInt(this.dataset.pieceIdx)); });
        cellEl.appendChild(el);
      }
    }
  });
}

// ── GAME LOGIC ───────────────────────────────────────────────────
function rollDice() {
  if (state.diceRolled || state.winner >= 0) return;
  
  var btn = document.getElementById('diceBtn');
  btn.classList.add('rolling');
  
  // Zvuk kocke
  playSound('roll');
  
  setTimeout(function() {
    btn.classList.remove('rolling');
    state.diceVal = Math.floor(Math.random() * 6) + 1;
    state.diceRolled = true;
    
    document.getElementById('diceResult').textContent = DICE_FACES[state.diceVal] + ' ' + state.diceVal;
    
    var movable = getMovablePieces();
    
    if (movable.length === 0) {
      // Nema poteza
      setMessage('Nema slobodnih figura za pomak ' + state.diceVal + '. Preskačeš potez!', '#e53935');
      setTimeout(nextTurn, 1500);
    } else if (movable.length === 1) {
      // Auto-odabir ako je samo jedna
      highlightPieces(movable);
      setInstruction('Samo jedna figura može se pomaknuti — klikni je!');
    } else {
      highlightPieces(movable);
      setInstruction('Odaberi figuru za pomak od ' + state.diceVal + ' polja');
    }
  }, 400);
}

function getMovablePieces() {
  var movable = [];
  var p = state.turn;
  var tl = config.trackLen;
  var midL = Math.floor(tl / 2) - 1;
  var midR = Math.floor(tl / 2);
  
  state.pieces.forEach(function(piece, idx) {
    if (piece.player !== p || piece.finished) return;
    
    if (piece.pos < 0) {
      // U tvrđavi — treba 6 za izlaz (klasično pravilo) ILI uvijek može (modernija varijanta)
      // Koristimo: uvijek može izaći (pristupačnije za djecu)
      movable.push(idx);
    } else {
      var newPos = piece.fromLeft ? piece.pos + state.diceVal : piece.pos - state.diceVal;
      // Može se pomaknuti ako ne prelazi cilj
      if (piece.fromLeft && newPos <= midR) movable.push(idx);
      if (!piece.fromLeft && newPos >= midL) movable.push(idx);
    }
  });
  return movable;
}

function highlightPieces(idxList) {
  document.querySelectorAll('.cell').forEach(function(c) { c.classList.remove('highlight'); });
  
  idxList.forEach(function(idx) {
    var piece = state.pieces[idx];
    if (piece.pos < 0) {
      // Highlight tvrđava figura
      var el = document.querySelector('.piece[data-piece-idx="'+idx+'"]');
      if (el) el.classList.add('selected');
    } else {
      var cell = document.querySelector('.cell[data-pos="' + piece.pos + '"]');
      if (cell) cell.classList.add('highlight');
    }
  });
}

function onPieceClick(pieceIdx) {
  var movable = getMovablePieces();
  if (!state.diceRolled || !movable.includes(pieceIdx)) return;
  movePiece(pieceIdx);
}

function onCellClick(pos) {
  if (!state.diceRolled) return;
  // Nađi figuru na tom polju
  var found = -1;
  state.pieces.forEach(function(piece, idx) {
    if (piece.player === state.turn && piece.pos === pos) found = idx;
  });
  if (found >= 0) onPieceClick(found);
}

function movePiece(pieceIdx) {
  var piece = state.pieces[pieceIdx];
  var tl = config.trackLen;
  var midL = Math.floor(tl / 2) - 1;
  var midR = Math.floor(tl / 2);
  
  playSound('move');
  
  // Pomakni
  if (piece.pos < 0) {
    // Izlaz iz tvrđave
    piece.pos = piece.fromLeft ? 0 : tl - 1;
  } else {
    piece.pos = piece.fromLeft ? piece.pos + state.diceVal : piece.pos - state.diceVal;
  }
  
  // Provjeri cilj
  var inGoal = (piece.pos === midL || piece.pos === midR);
  if (inGoal || (piece.fromLeft && piece.pos >= midL) || (!piece.fromLeft && piece.pos <= midR)) {
    piece.finished = true;
    piece.pos = piece.fromLeft ? midL : midR;
    state.finished[piece.player]++;
    
    playSound('goal');
    setMessage('⭐ ' + config.names[piece.player] + ' je stigao do cilja!', PLAYER_COLORS[piece.player]);
    
    // Provjeri pobjednika (sve 2 figure u cilju)
    if (state.finished[piece.player] >= 2) {
      setTimeout(function() { showWinner(piece.player); }, 800);
      placePieces();
      return;
    }
  }
  
  // Ruši li neku tuđu figuru?
  state.pieces.forEach(function(other, oIdx) {
    if (oIdx === pieceIdx || other.finished || other.player === piece.player) return;
    if (other.pos === piece.pos) {
      // Ruši!
      other.pos = -1; // Vrati u tvrđavu
      playSound('kick');
      setMessage('💥 ' + config.names[piece.player] + ' je srušio figuru ' + config.names[other.player] + '!', '#ff6f00');
    }
  });
  
  placePieces();
  
  // Mudrost na 6
  if (state.diceVal === 6) {
    var w = WISDOM[Math.floor(Math.random() * WISDOM.length)];
    setMessage('🎉 Šestica! ' + w, '#1D9E75');
    state.diceRolled = false; // Igrač baca ponovo
    setInstruction('Bacaj ponovo — dobijaš još jedan potez!');
  } else {
    setTimeout(nextTurn, 600);
  }
}

function nextTurn() {
  state.diceRolled = false;
  state.diceVal = 0;
  document.getElementById('diceResult').textContent = '—';
  document.querySelectorAll('.piece.selected').forEach(function(el) { el.classList.remove('selected'); });
  document.querySelectorAll('.cell.highlight').forEach(function(el) { el.classList.remove('highlight'); });
  
  state.turn = (state.turn + 1) % config.players;
  updateUI();
}

function updateUI() {
  var p = state.turn;
  var label = document.getElementById('turnLabel');
  label.textContent = '🎲 ' + config.names[p] + ' je na potezu';
  label.style.background = PLAYER_COLORS[p];
  setInstruction('Pritisni kocku za bacanje!');
  setMessage('', '');
}

function showWinner(p) {
  state.winner = p;
  document.getElementById('winText').textContent = '🏆 ' + config.names[p] + ' pobijedio!';
  document.getElementById('winMsg').textContent = WISDOM[Math.floor(Math.random() * WISDOM.length)];
  document.getElementById('winOverlay').classList.add('show');
  playSound('win');
}

function setMessage(msg, color) {
  var el = document.getElementById('messageBar');
  el.textContent = msg;
  el.style.background = msg ? color + '22' : 'transparent';
  el.style.color = color;
  el.style.border = msg ? '2px solid ' + color + '44' : 'none';
}

function setInstruction(txt) {
  document.getElementById('diceInstruction').textContent = txt;
}

function restartGame() {
  document.getElementById('winOverlay').classList.remove('show');
  document.getElementById('setupScreen').style.display = 'block';
  document.getElementById('gameScreen').style.display = 'none';
}

// ── ZVUK (Web Audio API, bez vanjskih fajlova) ────────────────────
var audioCtx = null;
function getAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}
function playSound(type) {
  try {
    var ctx = getAudio();
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    var configs = {
      roll:  {freq:[200,400,200], dur:0.3, type:'square'},
      move:  {freq:[300,500],     dur:0.15, type:'sine'},
      goal:  {freq:[400,600,800], dur:0.5, type:'sine'},
      kick:  {freq:[200,100],     dur:0.3, type:'sawtooth'},
      win:   {freq:[400,500,600,800], dur:0.8, type:'sine'},
    };
    var c = configs[type] || configs.move;
    osc.type = c.type;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + c.dur);
    c.freq.forEach(function(f, i) {
      osc.frequency.setValueAtTime(f, ctx.currentTime + i * (c.dur / c.freq.length));
    });
    osc.start(); osc.stop(ctx.currentTime + c.dur);
  } catch(e) {}
}

// ── INIT ─────────────────────────────────────────────────────────
renderNameInputs();
</script>
</body>
</html>
```

## VERIFIKACIJA
- [ ] Kocka baca nasumičan broj
- [ ] Figure izlaze iz tvrđave na klik
- [ ] Figure se pomiču po stazi
- [ ] Sudar ruši tuđu figuru u tvrđavu
- [ ] Šestica = još jedan potez
- [ ] Pobjednik se prikazuje kad 2 figure u cilju
- [ ] Radi na iPhone Safari (touch eventi)
- [ ] Sva tri načina duljine staze rade
- [ ] 2, 3 i 4 igrača rade

