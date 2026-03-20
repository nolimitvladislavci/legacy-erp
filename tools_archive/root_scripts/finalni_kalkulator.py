import os

CALC_FILE = '/var/www/fina-connect/templates/calculator/public_calculator.html'

new_content = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Angebotsrechner – LIMIT Connect</title>
<meta name="theme-color" content="#c9a84c">
<style>
:root{
  --gold:#c9a84c;--gold2:#b8962e;--gold-dim:rgba(201,168,76,.13);--gold-border:rgba(201,168,76,.3);
  --black:#09090b;--surface:#111118;--surface2:#18181f;--surface3:#22222c;--surface4:#2a2a36;
  --text:#e4e4ef;--text-dim:#7c7c99;--border:rgba(255,255,255,.07);
  --red:#ef4444;--green:#22c55e;--blue:#60a5fa;--purple:#a78bfa;
  --radius:10px;--shadow:0 4px 24px rgba(0,0,0,.45);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--black);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;font-size:14px}

/* ── HEADER ─────────────────────────────────────────────────────── */
.header{background:var(--surface);border-bottom:1px solid var(--gold-border);padding:13px 20px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100}
.hlogo{width:34px;height:34px;border-radius:8px;background:var(--gold-dim);border:1px solid var(--gold-border);display:flex;align-items:center;justify-content:center;font-weight:900;color:var(--gold);font-size:.9rem;flex-shrink:0}
.htitle{font-size:1rem;font-weight:800;color:var(--gold);line-height:1.1}
.hsub{font-size:.7rem;color:var(--text-dim)}
.hback{margin-left:auto;font-size:.75rem;color:var(--text-dim);text-decoration:none;padding:.3rem .8rem;border:1px solid var(--border);border-radius:6px;white-space:nowrap}
.hback:hover{color:var(--text);border-color:rgba(255,255,255,.2)}

/* ── LAYOUT ─────────────────────────────────────────────────────── */
.layout{display:flex;min-height:calc(100vh - 60px - 56px)}

/* ── SIDEBAR TABS ───────────────────────────────────────────────── */
.sidebar{width:152px;background:var(--surface);border-right:1px solid var(--border);flex-shrink:0;padding:12px 0}
.tab-btn{width:100%;background:none;border:none;color:var(--text-dim);padding:12px 16px;text-align:left;font-size:.8rem;cursor:pointer;display:flex;align-items:center;gap:9px;border-left:3px solid transparent;transition:all .15s;line-height:1.3}
.tab-btn:hover{background:rgba(255,255,255,.03);color:var(--text)}
.tab-btn.active{color:var(--gold);background:var(--gold-dim);border-left-color:var(--gold);font-weight:700}
.tab-icon{font-size:1.05rem;width:20px;text-align:center;flex-shrink:0}
.tab-num{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;font-size:.6rem;font-weight:800;margin-left:auto;background:rgba(255,255,255,.1);color:var(--text-dim);flex-shrink:0}
.tab-btn.active .tab-num{background:var(--gold);color:#000}

/* ── MAIN ───────────────────────────────────────────────────────── */
.main{flex:1;padding:20px 24px 16px;overflow-y:auto;max-width:1080px}
.tab-panel{display:none}
.tab-panel.active{display:block}

/* ── CARD ───────────────────────────────────────────────────────── */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;margin-bottom:14px}
.card-title{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.09em;color:var(--gold);margin-bottom:14px;display:flex;align-items:center;gap:7px}
.card-title span{color:var(--text-dim);font-weight:400;text-transform:none;letter-spacing:0;font-size:.75rem}

/* ── TABLE ──────────────────────────────────────────────────────── */
.tbl{width:100%;border-collapse:collapse}
.tbl th{font-size:.63rem;text-transform:uppercase;letter-spacing:.07em;color:var(--text-dim);padding:0 6px 9px;text-align:left;font-weight:700;white-space:nowrap;border-bottom:1px solid var(--border)}
.tbl th.r,.tbl td.r{text-align:right}
.tbl th.c,.tbl td.c{text-align:center}
.tbl td{padding:5px 6px;vertical-align:middle;border-bottom:1px solid rgba(255,255,255,.03)}
.tbl tbody tr:hover td{background:rgba(255,255,255,.015)}
.tbl tfoot td{border-top:1px solid var(--gold-border);padding-top:10px;font-weight:700}

/* ── COMPUTED CELL ──────────────────────────────────────────────── */
.comp{font-size:.8rem;font-weight:700;color:var(--gold);text-align:right;white-space:nowrap;background:var(--gold-dim);border-radius:5px;padding:4px 8px;min-width:90px;display:inline-block}
.comp-dim{font-size:.75rem;color:var(--text-dim);text-align:right;padding:4px 6px;min-width:80px;display:inline-block}

/* ── INPUTS ─────────────────────────────────────────────────────── */
input[type=number],input[type=text],select{
  background:var(--surface3);border:1px solid rgba(255,255,255,.1);border-radius:6px;
  color:var(--text);font-size:.82rem;padding:6px 8px;width:100%;outline:none;
  transition:border-color .15s;-moz-appearance:textfield;
}
input[type=number]::-webkit-inner-spin-button{-webkit-appearance:none}
input[type=number]:focus,input[type=text]:focus,select:focus{border-color:var(--gold-border);background:var(--surface4)}
select option{background:var(--surface3)}
input[type=range]{accent-color:var(--gold);width:100%;cursor:pointer;height:4px}
input[type=checkbox]{accent-color:var(--gold);width:16px;height:16px;cursor:pointer;flex-shrink:0}
.inp-sm{width:70px}
.inp-md{width:90px}
.inp-lg{width:130px}

/* ── BUTTONS ────────────────────────────────────────────────────── */
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;font-size:.78rem;font-weight:600;cursor:pointer;border:1px solid transparent;transition:all .15s}
.btn-add{background:rgba(255,255,255,.06);color:var(--text-dim);border-color:var(--border)}
.btn-add:hover{background:rgba(255,255,255,.1);color:var(--text)}
.btn-del{background:none;border:none;color:var(--red);cursor:pointer;font-size:.95rem;padding:3px 7px;opacity:.5;transition:opacity .15s}
.btn-del:hover{opacity:1}
.btn-gold{background:var(--gold);color:#000;font-weight:800;border-color:var(--gold)}
.btn-gold:hover{background:var(--gold2)}
.btn-outline{background:var(--gold-dim);color:var(--gold);border-color:var(--gold-border)}
.btn-outline:hover{background:rgba(201,168,76,.22)}
.btn-preset{background:var(--surface3);color:var(--text-dim);border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:.72rem;cursor:pointer;transition:all .15s}
.btn-preset:hover{border-color:var(--gold-border);color:var(--gold)}

/* ── SLIDER ROW ─────────────────────────────────────────────────── */
.sl-row{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.sl-label{font-size:.8rem;color:var(--text-dim);min-width:200px;flex-shrink:0}
.sl-val{font-size:.88rem;font-weight:800;color:var(--gold);min-width:52px;text-align:right;white-space:nowrap}

/* ── RESULT BOX ─────────────────────────────────────────────────── */
.rbox{background:linear-gradient(135deg,rgba(15,10,2,.8),rgba(9,9,20,.9));border:1px solid var(--gold-border);border-radius:var(--radius);padding:18px 20px;margin-top:14px}
.rrow{display:flex;align-items:baseline;justify-content:space-between;padding:5px 0;gap:12px}
.rrow:not(:last-child){border-bottom:1px solid rgba(255,255,255,.04)}
.rlabel{font-size:.8rem;color:var(--text-dim);flex:1}
.rval{font-size:.95rem;font-weight:700;color:var(--text);white-space:nowrap}
.rrow.total{border-top:1px solid var(--gold-border) !important;margin-top:6px;padding-top:12px}
.rrow.total .rlabel{color:var(--text);font-weight:600}
.rrow.total .rval{font-size:1.3rem;color:var(--gold)}
.rrow.sub .rval{color:var(--text-dim);font-size:.85rem}
.rrow.highlight .rval{color:var(--green);font-size:1.05rem}

/* ── KPI GRID ───────────────────────────────────────────────────── */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.kpi{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px 14px}
.kpi-label{font-size:.62rem;text-transform:uppercase;letter-spacing:.07em;color:var(--text-dim);margin-bottom:4px;font-weight:700}
.kpi-val{font-size:1.1rem;font-weight:800;color:var(--text)}
.kpi-val.gold{color:var(--gold)}
.kpi-val.green{color:var(--green)}
.kpi-val.blue{color:var(--blue)}

/* ── WORKER CARD ────────────────────────────────────────────────── */
.wcard{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:10px;position:relative}
.wcard-top{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.wcard-num{font-size:.65rem;font-weight:800;color:var(--text-dim);background:var(--surface3);border-radius:4px;padding:2px 7px}
.wcard-fields{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;margin-bottom:10px}
.field{display:flex;flex-direction:column;gap:4px}
.field label{font-size:.63rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-dim);font-weight:700}
.wcard-result{display:flex;gap:12px;flex-wrap:wrap;padding-top:10px;border-top:1px solid var(--border);margin-top:4px}
.wres{display:flex;flex-direction:column}
.wres-lbl{font-size:.62rem;color:var(--text-dim)}
.wres-val{font-size:.88rem;font-weight:700}

/* ── PONUDA PARAMS ──────────────────────────────────────────────── */
.param-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:16px}
.param-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:14px}
.param-card label{font-size:.63rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-dim);font-weight:700;display:block;margin-bottom:6px}
.param-card input{font-size:1.1rem;font-weight:800;text-align:center;padding:8px}

/* ── BREAKDOWN TABLE ────────────────────────────────────────────── */
.bdown{width:100%;border-collapse:collapse;margin-top:8px}
.bdown td{padding:7px 10px;font-size:.85rem;border-bottom:1px solid rgba(255,255,255,.04)}
.bdown td:last-child{text-align:right;font-weight:700;white-space:nowrap}
.bdown .section-hdr td{font-size:.65rem;text-transform:uppercase;letter-spacing:.07em;color:var(--text-dim);padding-top:14px;padding-bottom:4px;font-weight:800;border-bottom:1px solid var(--border)}
.bdown .sub-row td{color:var(--text-dim);font-size:.78rem}
.bdown .sub-row td:last-child{color:var(--text-dim)}
.bdown .total-row td{border-top:2px solid var(--gold-border) !important;font-size:1rem;font-weight:800;padding-top:12px}
.bdown .total-row td:last-child{color:var(--gold);font-size:1.1rem}
.bdown .bruto-row td{background:var(--gold-dim);border-radius:4px;padding-top:10px;padding-bottom:10px}
.bdown .bruto-row td:last-child{color:var(--gold);font-size:1.2rem}

/* ── TOTALS BAR ─────────────────────────────────────────────────── */
.bar{position:sticky;bottom:0;background:var(--surface);border-top:1px solid var(--gold-border);padding:8px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap;z-index:50}
.bar-item{display:flex;flex-direction:column}
.bar-lbl{font-size:.6rem;text-transform:uppercase;letter-spacing:.07em;color:var(--text-dim)}
.bar-val{font-size:.95rem;font-weight:800;color:var(--text)}
.bar-val.gold{color:var(--gold)}
.bar-sep{width:1px;background:var(--border);height:32px;flex-shrink:0}

/* ── PDV TOGGLE ─────────────────────────────────────────────────── */
.pdv-toggle{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--surface2);border:1px solid var(--border);border-radius:8px;cursor:pointer;margin-bottom:14px}
.pdv-toggle label{cursor:pointer;font-size:.82rem}

/* ── MOBILE ─────────────────────────────────────────────────────── */
@media(max-width:680px){
  .sidebar{width:48px}
  .tab-btn span:not(.tab-icon){display:none}
  .tab-num{display:none}
  .tab-btn{justify-content:center;padding:14px 0;border-left:none;border-bottom:3px solid transparent}
  .tab-btn.active{border-bottom-color:var(--gold);border-left:none;background:var(--gold-dim)}
  .main{padding:12px}
  .wcard-fields{grid-template-columns:1fr 1fr}
}
@media(max-width:480px){
  .kpi-grid{grid-template-columns:1fr 1fr}
  .param-grid{grid-template-columns:1fr 1fr}
}
</style>
</head>
<body>

<div class="header">
  <div class="hlogo">FC</div>
  <div>
    <div class="htitle">Angebotsrechner</div>
    <div class="hsub">Arbeitskräfte &middot; Kosten &middot; Angebot</div>
  </div>
  <a href="/bau/" class="hback">&#8592; Zurück</a>
</div>

<div class="layout">

  <nav class="sidebar">
    <button class="tab-btn active" onclick="switchTab('radnici',this)">
      <span class="tab-icon">👷</span>
      <span>Arbeitskräfte</span>
      <span class="tab-num" id="tn-radnici">0</span>
    </button>
    <button class="tab-btn" onclick="switchTab('troskovi',this)">
      <span class="tab-icon">🧱</span>
      <span>Kosten</span>
      <span class="tab-num" id="tn-troskovi">0</span>
    </button>
    <button class="tab-btn" onclick="switchTab('ponuda',this)">
      <span class="tab-icon">📋</span>
      <span>Angebot</span>
    </button>
  </nav>

  <main class="main">

    <div id="tab-radnici" class="tab-panel active">

      <div class="card">
        <div class="card-title">👷 Projektmitarbeiter
          <span>— Bruttostundenlohn + 17% LNK + Fahrtkosten + Überstunden</span>
        </div>

        <div id="workers-container"></div>

        <div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">
          <button class="btn btn-add" onclick="addWorker()">+ Mitarbeiter hinzufügen</button>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-left:auto">
            <span style="font-size:.68rem;color:var(--text-dim);align-self:center">Schnelleingabe:</span>
            <button class="btn-preset" onclick="addWorkerPreset(0)">Helfer</button>
            <button class="btn-preset" onclick="addWorkerPreset(2)">Facharbeiter</button>
            <button class="btn-preset" onclick="addWorkerPreset(4)">Meister</button>
            <button class="btn-preset" onclick="addWorkerPreset(6)">Bauleiter</button>
          </div>
        </div>
      </div>

      <div id="workers-kpis" class="kpi-grid" style="display:none">
        <div class="kpi">
          <div class="kpi-label">Gesamtzahl Mitarbeiter</div>
          <div class="kpi-val" id="kpi-nradnika">0</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Arbeitskosten/Stunde</div>
          <div class="kpi-val gold" id="kpi-trosak-sat">0,00 €/h</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Arbeitskosten/Tag</div>
          <div class="kpi-val gold" id="kpi-trosak-dan">0,00 €</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Fahrtkosten/Tag</div>
          <div class="kpi-val blue" id="kpi-prijevoz-dan">0,00 €</div>
        </div>
      </div>

      <div style="font-size:.72rem;color:var(--text-dim);background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px 14px;line-height:1.8">
        <strong style="color:var(--text)">Berechnungsformel pro Mitarbeiter:</strong><br>
        Tatsächliche Kosten/Stunde = (Brutto + 17% LNK) × (1 + Überstunden%) + Fahrtkosten/Stunde<br>
        <span style="color:var(--text-dim)">wobei: Fahrtkosten/Stunde = Spesen/Tag ÷ Stunden/Tag</span>
      </div>
    </div>

    <div id="tab-troskovi" class="tab-panel">

      <div class="card">
        <div class="card-title">🧱 Material & Beschaffung</div>
        <table class="tbl" id="mat-table">
          <thead>
            <tr>
              <th style="width:28px">#</th>
              <th>Bezeichnung / Beschreibung</th>
              <th class="r" style="width:110px">Betrag (€)</th>
              <th style="width:36px"></th>
            </tr>
          </thead>
          <tbody id="mat-body"></tbody>
          <tfoot>
            <tr>
              <td colspan="2" style="font-size:.78rem;color:var(--text-dim)">Gesamt Material:</td>
              <td class="r"><span class="comp" id="mat-total">0,00 €</span></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
        <div style="margin-top:12px">
          <button class="btn btn-add" onclick="addMaterial()">+ Position hinzufügen</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">🏗️ Maschinen- & Geräteverleih</div>
        <table class="tbl" id="stroj-table">
          <thead>
            <tr>
              <th style="width:28px">#</th>
              <th>Maschine / Gerät</th>
              <th class="r" style="width:100px">€/Tag</th>
              <th class="r" style="width:80px">Tage</th>
              <th class="r" style="width:110px">Gesamt</th>
              <th style="width:36px"></th>
            </tr>
          </thead>
          <tbody id="stroj-body"></tbody>
          <tfoot>
            <tr>
              <td colspan="4" style="font-size:.78rem;color:var(--text-dim)">Gesamt Verleih:</td>
              <td class="r"><span class="comp" id="stroj-total">0,00 €</span></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-add" onclick="addStroj()">+ Maschine hinzufügen</button>
          <button class="btn-preset" onclick="addStrojPreset('Minibagger',35)">Minibagger €35/Tag</button>
          <button class="btn-preset" onclick="addStrojPreset('Bagger',65)">Bagger €65/Tag</button>
          <button class="btn-preset" onclick="addStrojPreset('Kran',90)">Kran €90/Tag</button>
          <button class="btn-preset" onclick="addStrojPreset('LKW',55)">LKW €55/Tag</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title">⚙️ Regiekosten & Gewinnmarge</div>
        <p style="font-size:.78rem;color:var(--text-dim);margin-bottom:18px">
          Die Regiekosten werden auf die direkten Gesamtkosten (Arbeit + Maschine + Material) aufgeschlagen.<br>
          Die Gewinnmarge/Provision wird auf die Summe aus Kosten + Regiekosten berechnet.
        </p>

        <div class="sl-row">
          <span class="sl-label">⚙️ Regiekosten (%)</span>
          <input type="range" min="5" max="30" step="0.5" id="sl-rezije" value="15" oninput="syncSlider('rezije');recalc()">
          <span class="sl-val" id="sv-rezije">15%</span>
        </div>
        <div style="font-size:.7rem;color:var(--text-dim);margin-bottom:18px;margin-top:-6px;margin-left:212px">
          Fahrzeuge, Werkzeuge, Büromiete, Verwaltung, Versicherungen...
        </div>

        <div class="sl-row">
          <span class="sl-label">💰 Gewinnmarge (%)</span>
          <input type="range" min="10" max="40" step="1" id="sl-zarada" value="20" oninput="syncSlider('zarada');recalc()">
          <span class="sl-val" id="sv-zarada">20%</span>
        </div>
        <div style="font-size:.7rem;color:var(--text-dim);margin-bottom:8px;margin-top:-6px;margin-left:212px">
          Unternehmensgewinn / Projektmanagementgebühr
        </div>

        <div class="rbox">
          <div class="rrow sub">
            <span class="rlabel">Direkte Kosten (Arbeit + Maschine + Material)</span>
            <span class="rval" id="rez-direktni">0,00 €</span>
          </div>
          <div class="rrow sub">
            <span class="rlabel">Regiekosten (<span id="rez-pct">15</span>%)</span>
            <span class="rval" id="rez-iznos">0,00 €</span>
          </div>
          <div class="rrow">
            <span class="rlabel">Kosten + Regiekosten</span>
            <span class="rval" id="rez-sbrez">0,00 €</span>
          </div>
          <div class="rrow sub">
            <span class="rlabel">Gewinnmarge (<span id="rez-zarada-pct">20</span>%)</span>
            <span class="rval" id="rez-zarada">0,00 €</span>
          </div>
          <div class="rrow total">
            <span class="rlabel">💰 GESAMT NETTO (ohne MwSt.)</span>
            <span class="rval" id="rez-neto">0,00 €</span>
          </div>
        </div>
      </div>
    </div>

    <div id="tab-ponuda" class="tab-panel">

      <div class="card">
        <div class="card-title">📋 Projektparameter</div>
        <div class="param-grid">
          <div class="param-card">
            <label>Anzahl Arbeitstage</label>
            <input type="number" id="p-dani" value="5" min="1" max="999" step="1"
                   oninput="recalc()" style="font-size:1.3rem;font-weight:800;text-align:center">
          </div>
          <div class="param-card">
            <label>Stunden pro Tag</label>
            <input type="number" id="p-sati" value="8" min="1" max="24" step="0.5"
                   oninput="recalc()" style="font-size:1.3rem;font-weight:800;text-align:center">
          </div>
          <div class="param-card">
            <label>Regiekosten %</label>
            <input type="number" id="p-rezije-inp" value="15" min="0" max="100" step="0.5"
                   oninput="syncFromInput('rezije');recalc()" style="font-size:1.3rem;font-weight:800;text-align:center">
          </div>
          <div class="param-card">
            <label>Gewinnmarge %</label>
            <input type="number" id="p-zarada-inp" value="20" min="0" max="100" step="1"
                   oninput="syncFromInput('zarada');recalc()" style="font-size:1.3rem;font-weight:800;text-align:center">
          </div>
        </div>

        <label class="pdv-toggle">
          <input type="checkbox" id="pdv-toggle" onchange="recalc()">
          <span>Berechnung inkl. MwSt. anzeigen (19%)</span>
          <span style="margin-left:auto;font-size:.72rem;color:var(--text-dim)">Für Privatkunden (B2C)</span>
        </label>
      </div>

      <div class="kpi-grid">
        <div class="kpi">
          <div class="kpi-label">Gesamtstunden</div>
          <div class="kpi-val" id="kpi-total-sati">0 h</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Arbeitskosten</div>
          <div class="kpi-val" id="kpi-trad">0,00 €</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Material + Maschine</div>
          <div class="kpi-val" id="kpi-tmat">0,00 €</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Stundensatz</div>
          <div class="kpi-val gold" id="kpi-csat">0,00 €/h</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Tagessatz</div>
          <div class="kpi-val gold" id="kpi-cdan">0,00 €/Tag</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Angebot NETTO</div>
          <div class="kpi-val green" id="kpi-ponuda-neto">0,00 €</div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">📊 Vollständige Aufschlüsselung</div>
        <table class="bdown">
          <tbody>
            <tr class="section-hdr"><td colspan="2">PERSONAL</td></tr>
            <tr id="brow-radnici" class="sub-row"><td id="bd-rad-desc">—</td><td id="bd-rad">0,00 €</td></tr>
            <tr id="brow-prijevoz" class="sub-row"><td>Fahrtkosten / Spesen</td><td id="bd-prijevoz">0,00 €</td></tr>

            <tr class="section-hdr"><td colspan="2">MASCHINEN & GERÄTE</td></tr>
            <tr id="brow-stroj" class="sub-row"><td>Verleihkosten</td><td id="bd-stroj">0,00 €</td></tr>

            <tr class="section-hdr"><td colspan="2">MATERIAL</td></tr>
            <tr id="brow-mat" class="sub-row"><td>Material & Beschaffung</td><td id="bd-mat">0,00 €</td></tr>

            <tr class="section-hdr"><td colspan="2">KOSTENÜBERSICHT</td></tr>
            <tr class="sub-row"><td>Direkte Gesamtkosten</td><td id="bd-direktni">0,00 €</td></tr>
            <tr class="sub-row"><td>+ Regiekosten (<span id="bd-rezpct">15</span>%)</td><td id="bd-rezije">0,00 €</td></tr>
            <tr><td style="font-weight:700">Kosten + Regiekosten</td><td id="bd-sbrez" style="font-weight:700">0,00 €</td></tr>
            <tr class="sub-row"><td>+ Gewinnmarge (<span id="bd-zpct">20</span>%)</td><td id="bd-zarada">0,00 €</td></tr>

            <tr class="total-row">
              <td>💰 GESAMT NETTO</td>
              <td id="bd-neto">0,00 €</td>
            </tr>
            <tr id="brow-pdv" class="sub-row" style="display:none">
              <td>+ MwSt. 19%</td>
              <td id="bd-pdv">0,00 €</td>
            </tr>
            <tr id="brow-bruto" class="bruto-row" style="display:none">
              <td>💶 GESAMT BRUTTO (inkl. MwSt.)</td>
              <td id="bd-bruto">0,00 €</td>
            </tr>

            <tr class="section-hdr"><td colspan="2">STUNDEN & TAGESÄTZE</td></tr>
            <tr class="sub-row"><td>Nettopreis pro Stunde</td><td id="bd-csat">0,00 €/h</td></tr>
            <tr class="sub-row" id="brow-brutosat" style="display:none"><td>Bruttopreis pro Stunde</td><td id="bd-bsat">0,00 €/h</td></tr>
            <tr class="sub-row"><td>Nettopreis pro Tag</td><td id="bd-cdan">0,00 €/Tag</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card" style="border-color:var(--gold-border)">
        <div class="card-title">📤 Projektanfrage senden</div>
        <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:12px">
          <input type="text" id="upit-title" placeholder="Projektname (z.B. Badsanierung)" style="font-size:.88rem">
          <input type="text" id="upit-location" placeholder="Standort (Stadt, Adresse)">
        </div>
        <button class="btn btn-gold" onclick="sendToUpit()" style="width:100%;justify-content:center;padding:12px">
          📤 Projektanfrage senden →
        </button>
        <p style="font-size:.7rem;color:var(--text-dim);margin-top:8px;text-align:center">
          Öffnet ein Formular mit automatisch ausgefüllten Beträgen und einer Beschreibung der Berechnung.
        </p>
      </div>
    </div>

  </main>
</div>

<div class="bar">
  <div class="bar-item">
    <span class="bar-lbl">👷 Arbeit/h</span>
    <span class="bar-val" id="bar-rsat">0,00 €/h</span>
  </div>
  <div class="bar-sep"></div>
  <div class="bar-item">
    <span class="bar-lbl">🧱 Material</span>
    <span class="bar-val" id="bar-mat">0,00 €</span>
  </div>
  <div class="bar-item">
    <span class="bar-lbl">🏗️ Maschinen</span>
    <span class="bar-val" id="bar-stroj">0,00 €</span>
  </div>
  <div class="bar-sep"></div>
  <div class="bar-item">
    <span class="bar-lbl">📋 Nettoangebot</span>
    <span class="bar-val gold" id="bar-neto">0,00 €</span>
  </div>
  <div class="bar-item">
    <span class="bar-lbl">💶 Brutto (inkl. MwSt)</span>
    <span class="bar-val gold" id="bar-bruto" style="color:var(--text-dim)">—</span>
  </div>
  <div style="margin-left:auto">
    <button class="btn btn-outline" onclick="switchTab('ponuda',document.querySelector('.tab-btn:last-child'))">
      Angebot →
    </button>
  </div>
</div>

<script>
// ═══════════════════════════════════════════════════════════════════
//  KATEGORIJE RADNIKA — bruto €/h
// ═══════════════════════════════════════════════════════════════════
var KATEGORIJE = [
  {label:'Helfer (Ungelernt)',        bruto:12.5},
  {label:'Angelernte Kraft',          bruto:14.5},
  {label:'Facharbeiter I',            bruto:17.0},
  {label:'Facharbeiter II',           bruto:20.0},
  {label:'Meister',                   bruto:24.0},
  {label:'Spezialist',                bruto:29.0},
  {label:'Bauleiter / Aufseher',      bruto:35.0},
];

var DOPRINOS = 0.17; 

// ═══════════════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════════════
var S = {
  workers:   [],  
  materials: [],  
  strojevi:  [],  
};

// ═══════════════════════════════════════════════════════════════════
//  TABS
// ═══════════════════════════════════════════════════════════════════
function switchTab(name, btn) {
  document.querySelectorAll('.tab-panel').forEach(function(p){p.classList.remove('active');});
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
  document.getElementById('tab-'+name).classList.add('active');
  if (btn) btn.classList.add('active');
  recalc();
}

// ═══════════════════════════════════════════════════════════════════
//  WORKERS
// ═══════════════════════════════════════════════════════════════════
function addWorker(kat, bruto, count, prijevoz, overtime) {
  var k = kat !== undefined ? kat : 2;
  S.workers.push({
    kat:      k,
    bruto:    bruto    !== undefined ? bruto    : KATEGORIJE[k].bruto,
    count:    count    !== undefined ? count    : 1,
    prijevoz: prijevoz !== undefined ? prijevoz : 0,
    overtime: overtime !== undefined ? overtime : 0,
  });
  renderWorkers();
  recalc();
}

function addWorkerPreset(kat) { addWorker(kat); }

function removeWorker(i) {
  S.workers.splice(i, 1);
  renderWorkers();
  recalc();
}

function updateWorker(i, field, val) {
  S.workers[i][field] = val;
  if (field === 'kat') {
    S.workers[i].bruto = KATEGORIJE[val].bruto;
    renderWorkers();
  }
  recalc();
}

function workerRealCostPerH(w) {
  var satiDan = parseFloat(document.getElementById('p-sati').value) || 8;
  var brutoTotal = w.bruto * (1 + DOPRINOS); 
  var otFactor   = 1 + (w.overtime / 100);
  var transport  = w.prijevoz / satiDan; 
  return brutoTotal * otFactor + transport;
}

function renderWorkers() {
  var container = document.getElementById('workers-container');
  var satiDan = parseFloat(document.getElementById('p-sati').value) || 8;

  if (!S.workers.length) {
    container.innerHTML = '<div style="color:var(--text-dim);font-size:.82rem;padding:10px 4px">Keine Mitarbeiter — klicken Sie auf "+ Mitarbeiter hinzufügen".</div>';
    document.getElementById('workers-kpis').style.display = 'none';
    return;
  }

  document.getElementById('workers-kpis').style.display = 'grid';

  container.innerHTML = S.workers.map(function(w, i) {
    var doprinos    = w.bruto * DOPRINOS;
    var brutoPlusDop= w.bruto + doprinos;
    var otFactor    = 1 + w.overtime / 100;
    var transport   = w.prijevoz / satiDan;
    var realH       = brutoPlusDop * otFactor + transport; 
    var realDan     = realH * w.count * satiDan;

    var katOpts = KATEGORIJE.map(function(k, ki) {
      return '<option value="'+ki+'"'+(w.kat===ki?' selected':'')+'>'+k.label+'</option>';
    }).join('');

    return '<div class="wcard" id="wcard-'+i+'">' +

      '<div class="wcard-top">' +
        '<span class="wcard-num">MITARBEITER '+(i+1)+'</span>' +
        '<button class="btn-del" onclick="removeWorker('+i+')" title="Entfernen">✕</button>' +
      '</div>' +

      '<div class="wcard-fields">' +
        '<div class="field" style="grid-column:span 2">' +
          '<label>Kategorie</label>' +
          '<select onchange="updateWorker('+i+',\'kat\',parseInt(this.value))">' +
            katOpts +
          '</select>' +
        '</div>' +
        '<div class="field">' +
          '<label>Brutto (€/h)</label>' +
          '<input type="number" min="5" max="300" step="0.5" value="'+w.bruto+'"' +
          ' onchange="updateWorker('+i+',\'bruto\',parseFloat(this.value)||0)">' +
        '</div>' +
        '<div class="field">' +
          '<label>Anzahl</label>' +
          '<input type="number" min="1" max="100" step="1" value="'+w.count+'"' +
          ' onchange="updateWorker('+i+',\'count\',parseInt(this.value)||1)">' +
        '</div>' +
        '<div class="field">' +
          '<label>Fahrtkosten (€/Tag)</label>' +
          '<input type="number" min="0" max="500" step="0.5" value="'+w.prijevoz+'"' +
          ' onchange="updateWorker('+i+',\'prijevoz\',parseFloat(this.value)||0)">' +
        '</div>' +
        '<div class="field">' +
          '<label>Überstunden (%)</label>' +
          '<input type="number" min="0" max="200" step="5" value="'+w.overtime+'"' +
          ' onchange="updateWorker('+i+',\'overtime\',parseFloat(this.value)||0)">' +
        '</div>' +
      '</div>' +

      '<div class="wcard-result">' +
        '<div class="wres">' +
          '<span class="wres-lbl">Brutto + LNK 17%</span>' +
          '<span class="wres-val" style="color:var(--text-dim)">'+fmt(brutoPlusDop)+' €/h</span>' +
        '</div>' +
        (w.overtime > 0 ? '<div class="wres"><span class="wres-lbl">Überstunden-Faktor</span><span class="wres-val" style="color:var(--text-dim)">×'+otFactor.toFixed(2)+'</span></div>' : '') +
        (w.prijevoz > 0 ? '<div class="wres"><span class="wres-lbl">Fahrtkosten/Stunde</span><span class="wres-val" style="color:var(--blue)">+'+fmt(transport)+' €/h</span></div>' : '') +
        '<div class="wres" style="margin-left:auto">' +
          '<span class="wres-lbl">⭐ Tatsächliche Kosten/h</span>' +
          '<span class="wres-val" style="color:var(--gold);font-size:1rem">'+fmt(realH)+' €/h</span>' +
        '</div>' +
        '<div class="wres">' +
          '<span class="wres-lbl">× '+w.count+' Pers. × '+satiDan+'h/Tag</span>' +
          '<span class="wres-val" style="color:var(--gold)">'+fmt(realDan)+' €/Tag</span>' +
        '</div>' +
      '</div>' +

    '</div>';
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════
//  MATERIALS
// ═══════════════════════════════════════════════════════════════════
function addMaterial(naziv, iznos) {
  S.materials.push({naziv: naziv||'', iznos: iznos||0});
  renderMaterials();
  recalc();
}

function removeMaterial(i) {
  S.materials.splice(i,1);
  renderMaterials();
  recalc();
}

function updateMaterial(i, field, val) {
  S.materials[i][field] = val;
  recalc();
}

function renderMaterials() {
  var tbody = document.getElementById('mat-body');
  if (!S.materials.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-dim);font-size:.78rem;padding:10px 6px">Keine Materialien — klicken Sie auf "+ Position hinzufügen"</td></tr>';
    return;
  }
  tbody.innerHTML = S.materials.map(function(m, i) {
    return '<tr>'+
      '<td style="color:var(--text-dim);font-size:.72rem">'+(i+1)+'</td>'+
      '<td><input type="text" value="'+esc(m.naziv)+'" placeholder="Materialbezeichnung"'+
          ' onchange="updateMaterial('+i+',\'naziv\',this.value)"></td>'+
      '<td><input type="number" min="0" step="0.01" value="'+m.iznos+'"'+
          ' onchange="updateMaterial('+i+',\'iznos\',parseFloat(this.value)||0)"'+
          ' class="inp-md" style="text-align:right"></td>'+
      '<td><button class="btn-del" onclick="removeMaterial('+i+')">✕</button></td>'+
    '</tr>';
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════
//  STROJEVI
// ═══════════════════════════════════════════════════════════════════
function addStroj(naziv, rate, dani) {
  var d = parseInt(document.getElementById('p-dani').value)||5;
  S.strojevi.push({naziv: naziv||'', rate: rate||0, dani: dani!==undefined?dani:d});
  renderStrojevi();
  recalc();
}

function addStrojPreset(naziv, rate) { addStroj(naziv, rate); }

function removeStroj(i) {
  S.strojevi.splice(i,1);
  renderStrojevi();
  recalc();
}

function updateStroj(i, field, val) {
  S.strojevi[i][field] = val;
  recalc();
  renderStrojevi();
}

function renderStrojevi() {
  var tbody = document.getElementById('stroj-body');
  if (!S.strojevi.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-dim);font-size:.78rem;padding:10px 6px">Keine Maschinen — klicken Sie auf "+ Maschine hinzufügen"</td></tr>';
    return;
  }
  tbody.innerHTML = S.strojevi.map(function(s, i) {
    var total = s.rate * s.dani;
    return '<tr>'+
      '<td style="color:var(--text-dim);font-size:.72rem">'+(i+1)+'</td>'+
      '<td><input type="text" value="'+esc(s.naziv)+'" placeholder="Maschine / Gerät"'+
          ' onchange="updateStroj('+i+',\'naziv\',this.value)"></td>'+
      '<td><input type="number" min="0" step="0.5" value="'+s.rate+'"'+
          ' onchange="updateStroj('+i+',\'rate\',parseFloat(this.value)||0)"'+
          ' class="inp-md" style="text-align:right"></td>'+
      '<td><input type="number" min="1" step="1" value="'+s.dani+'"'+
          ' onchange="updateStroj('+i+',\'dani\',parseInt(this.value)||1)"'+
          ' class="inp-sm" style="text-align:right"></td>'+
      '<td class="r"><span class="comp-dim">'+fmt(total)+' €</span></td>'+
      '<td><button class="btn-del" onclick="removeStroj('+i+')">✕</button></td>'+
    '</tr>';
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════
//  SLIDERS
// ═══════════════════════════════════════════════════════════════════
function syncSlider(key) {
  var sl  = document.getElementById('sl-'+key);
  var inp = document.getElementById('p-'+key+'-inp');
  var sv  = document.getElementById('sv-'+key);
  if (sl && inp) inp.value = sl.value;
  if (sv) sv.textContent = sl.value + '%';
}

function syncFromInput(key) {
  var inp = document.getElementById('p-'+key+'-inp');
  var sl  = document.getElementById('sl-'+key);
  var sv  = document.getElementById('sv-'+key);
  var v = parseFloat(inp.value) || 0;
  if (sl) sl.value = Math.min(Math.max(v, parseFloat(sl.min)), parseFloat(sl.max));
  if (sv) sv.textContent = v.toFixed(1) + '%';
}

// ═══════════════════════════════════════════════════════════════════
//  RECALCULATE
// ═══════════════════════════════════════════════════════════════════
function recalc() {
  var dani    = parseFloat(document.getElementById('p-dani').value)  || 5;
  var satiDan = parseFloat(document.getElementById('p-sati').value)  || 8;
  var rezPct  = parseFloat(document.getElementById('p-rezije-inp').value) || 15;
  var zarPct  = parseFloat(document.getElementById('p-zarada-inp').value) || 20;
  var pdvOn   = document.getElementById('pdv-toggle').checked;

  var sv_rez = document.getElementById('sv-rezije');
  var sv_zar = document.getElementById('sv-zarada');
  if (sv_rez) sv_rez.textContent = rezPct.toFixed(1) + '%';
  if (sv_zar) sv_zar.textContent = zarPct.toFixed(0) + '%';

  var totalCostRadPerH = 0;   
  var totalPrijevoz    = 0;   
  var totalRadnici     = 0;

  S.workers.forEach(function(w) {
    var realH = workerRealCostPerH(w); 
    totalCostRadPerH += realH * w.count;
    totalPrijevoz    += w.prijevoz * w.count;
    totalRadnici     += w.count;
  });

  var totalSati    = dani * satiDan;
  var costRad      = totalCostRadPerH * totalSati - totalPrijevoz * dani;
  var costRadNoPrev = S.workers.reduce(function(acc, w) {
    var brutoTotal = w.bruto * (1 + DOPRINOS) * (1 + w.overtime/100);
    return acc + brutoTotal * w.count * totalSati;
  }, 0);
  var costPrijevoz = totalPrijevoz * dani;

  var costMat = S.materials.reduce(function(s,m){return s+m.iznos;}, 0);
  var costStroj = S.strojevi.reduce(function(s,m){return s+m.rate*m.dani;}, 0);

  var direktni  = costRadNoPrev + costPrijevoz + costStroj + costMat;
  var rezije    = direktni * (rezPct / 100);
  var sbRez     = direktni + rezije;
  var zarada    = sbRez * (zarPct / 100);
  var neto      = sbRez + zarada;
  var pdv       = neto * 0.19; // 19% MwSt DE
  var bruto     = neto + pdv;

  var csatNeto  = totalSati > 0 ? neto / totalSati : 0;
  var csatBruto = totalSati > 0 ? bruto / totalSati : 0;
  var cdanNeto  = dani > 0 ? neto / dani : 0;

  setText('kpi-nradnika',    totalRadnici);
  setText('kpi-trosak-sat',  fmt(totalCostRadPerH) + ' €/h');
  setText('kpi-trosak-dan',  fmt(totalCostRadPerH * satiDan) + ' €');
  setText('kpi-prijevoz-dan',fmt(totalPrijevoz) + ' €');

  setText('tn-radnici', S.workers.length || '');
  setText('tn-troskovi', (S.materials.length + S.strojevi.length) || '');

  setText('mat-total',   fmt(costMat)   + ' €');
  setText('stroj-total', fmt(costStroj) + ' €');
  setText('rez-direktni',fmt(direktni)  + ' €');
  setText('rez-pct',     rezPct.toFixed(1));
  setText('rez-iznos',   fmt(rezije)    + ' €');
  setText('rez-sbrez',   fmt(sbRez)     + ' €');
  setText('rez-zarada-pct', zarPct.toFixed(0));
  setText('rez-zarada',  fmt(zarada)    + ' €');
  setText('rez-neto',    fmt(neto)      + ' €');

  setText('kpi-total-sati', totalSati + ' h');
  setText('kpi-trad',       fmt(costRadNoPrev + costPrijevoz) + ' €');
  setText('kpi-tmat',       fmt(costMat + costStroj) + ' €');
  setText('kpi-csat',       fmt(csatNeto) + ' €/h');
  setText('kpi-cdan',       fmt(cdanNeto) + ' €/Tag');
  setText('kpi-ponuda-neto',fmt(neto) + ' €');

  var radDesc = totalRadnici + ' Pers. × ' + satiDan + 'h × ' + dani + ' Tage';
  setText('bd-rad-desc',  radDesc);
  setText('bd-rad',       fmt(costRadNoPrev) + ' €');
  setText('bd-prijevoz',  fmt(costPrijevoz)  + ' €');
  setText('bd-stroj',     fmt(costStroj)     + ' €');
  setText('bd-mat',       fmt(costMat)       + ' €');
  setText('bd-direktni',  fmt(direktni)      + ' €');
  setText('bd-rezpct',    rezPct.toFixed(1));
  setText('bd-rezije',    fmt(rezije)        + ' €');
  setText('bd-sbrez',     fmt(sbRez)         + ' €');
  setText('bd-zpct',      zarPct.toFixed(0));
  setText('bd-zarada',    fmt(zarada)        + ' €');
  setText('bd-neto',      fmt(neto)          + ' €');
  setText('bd-pdv',       fmt(pdv)           + ' €');
  setText('bd-bruto',     fmt(bruto)         + ' €');
  setText('bd-csat',      fmt(csatNeto)      + ' €/h');
  setText('bd-bsat',      fmt(csatBruto)     + ' €/h');
  setText('bd-cdan',      fmt(cdanNeto)      + ' €/Tag');

  show('brow-pdv',    pdvOn);
  show('brow-bruto',  pdvOn);
  show('brow-brutosat', pdvOn);

  setText('bar-rsat',  fmt(totalCostRadPerH) + ' €/h');
  setText('bar-mat',   fmt(costMat)   + ' €');
  setText('bar-stroj', fmt(costStroj) + ' €');
  setText('bar-neto',  fmt(neto)      + ' €');
  if (pdvOn) {
    setText('bar-bruto', fmt(bruto) + ' €');
    document.getElementById('bar-bruto').style.color = 'var(--gold)';
  } else {
    setText('bar-bruto', '—');
    document.getElementById('bar-bruto').style.color = 'var(--text-dim)';
  }

  renderWorkers();
}

function sendToUpit() {
  var dani    = parseFloat(document.getElementById('p-dani').value)||5;
  var satiDan = parseFloat(document.getElementById('p-sati').value)||8;
  var rezPct  = parseFloat(document.getElementById('p-rezije-inp').value)||15;
  var zarPct  = parseFloat(document.getElementById('p-zarada-inp').value)||20;

  var totalCostPerH = S.workers.reduce(function(acc,w){return acc+workerRealCostPerH(w)*w.count;},0);
  var totalSati     = dani * satiDan;
  var costRadNoPrev = S.workers.reduce(function(acc,w){
    return acc + w.bruto*(1+DOPRINOS)*(1+w.overtime/100)*w.count*totalSati;
  },0);
  var costPrijevoz  = S.workers.reduce(function(acc,w){return acc+w.prijevoz*w.count*dani;},0);
  var costMat       = S.materials.reduce(function(s,m){return s+m.iznos;},0);
  var costStroj     = S.strojevi.reduce(function(s,m){return s+m.rate*m.dani;},0);
  var direktni      = costRadNoPrev + costPrijevoz + costStroj + costMat;
  var sbRez         = direktni * (1 + rezPct/100);
  var neto          = sbRez * (1 + zarPct/100);

  var title    = document.getElementById('upit-title').value.trim() || 'Projektangebot';
  var location = document.getElementById('upit-location').value.trim();

  var lines = ['Kalkulation – LIMIT Connect:', ''];
  lines.push('Projekt: ' + dani + ' Arbeitstage × ' + satiDan + 'h = ' + totalSati + 'h gesamt');
  lines.push('');

  if (S.workers.length) {
    lines.push('PERSONAL:');
    S.workers.forEach(function(w){
      var kat = KATEGORIJE[w.kat] ? KATEGORIJE[w.kat].label : '';
      var rh = workerRealCostPerH(w);
      lines.push('  '+w.count+'× '+kat+' | Brutto: '+w.bruto+'€/h | Tatsächliche Kosten: '+fmt(rh)+'€/h'+(w.prijevoz?' | Fahrtkosten: '+w.prijevoz+'€/Tag':'')+(w.overtime?' | OT: +'+w.overtime+'%':''));
    });
    lines.push('');
  }
  if (S.strojevi.length) {
    lines.push('MASCHINEN:');
    S.strojevi.forEach(function(s){lines.push('  '+(s.naziv||'Maschine')+': '+s.rate+'€/Tag × '+s.dani+' Tage = '+fmt(s.rate*s.dani)+'€');});
    lines.push('');
  }
  if (S.materials.length) {
    lines.push('MATERIAL:');
    S.materials.forEach(function(m){lines.push('  '+(m.naziv||'Position')+': '+fmt(m.iznos)+'€');});
    lines.push('');
  }
  lines.push('Direkte Kosten: '+fmt(direktni)+'€');
  lines.push('+ Regiekosten '+rezPct+'%: '+fmt(direktni*rezPct/100)+'€');
  lines.push('+ Gewinnmarge '+zarPct+'%: '+fmt(sbRez*zarPct/100)+'€');
  lines.push('= NETTO Angebot: '+fmt(neto)+'€');

  var params = new URLSearchParams({
    title:       title,
    description: lines.join('\n'),
    location:    location,
    budget_from: Math.round(neto * 0.9),
    budget_to:   Math.round(neto * 1.15),
  });
  window.open('/burza/upit/?' + params.toString(), '_blank');
}

function fmt(n) {
  return (Math.round(n*100)/100).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2});
}
function setText(id, val) { var el=document.getElementById(id); if(el) el.textContent=val; }
function show(id, visible) { var el=document.getElementById(id); if(el) el.style.display=visible?'':'none'; }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

(function init() {
  addWorker(2, undefined, 2, 15, 0);   
  addWorker(0, undefined, 1, 0,  0);   

  addMaterial('Sand / Kies', 280);
  addMaterial('Zement / Bindemittel', 150);

  renderMaterials();
  renderStrojevi();
  recalc();
})();
</script>
</body>
</html>
"""

with open(CALC_FILE, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Kalkulator je u potpunosti prebrisan čistom njemačkom verzijom! Osvježite preglednik.")
