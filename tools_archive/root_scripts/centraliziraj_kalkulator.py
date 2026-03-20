import os
import shutil

BASE_DIR = '/var/www/fina-connect'
CSS_DIR = os.path.join(BASE_DIR, 'static', 'css')
CALC_TEMPLATE = os.path.join(BASE_DIR, 'templates', 'calculator', 'public_calculator.html')

# 1. Kreiranje mape za CSS ako ne postoji
os.makedirs(CSS_DIR, exist_ok=True)

# 2. Kreiranje globalne datoteke s temama (global_themes.css)
global_css_content = """/* ==========================================================================
   VISKOVIĆ GROUP ERP - GLOBAL THEMES
   Ova datoteka sadrži sve CSS varijable za teme. Ne definirajte ih u HTML-u!
   ========================================================================== */

/* 1. DEFAULT THEME (Dark / Gold - Visković Premium) */
:root {
    --gold: #c9a84c;
    --gold2: #e8c96a; /* Svjetlija varijanta za hover */
    --gold-dim: rgba(201, 168, 76, 0.12);
    --gold-border: rgba(201, 168, 76, 0.28);
    
    --black: #0a0a0a;
    --dark: #111214;
    --surface: #181a1d;
    --surface2: #1e293b;
    --surface3: #22222c;
    
    --border: #252830;
    --border-light: rgba(255, 255, 255, 0.08);
    
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --muted: #4a5060;
    
    --green: #10b981;
    --red: #ef4444;
    --amber: #f59e0b;
    --blue: #3b82f6;
    
    --radius: 10px;
    --shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
    
    /* Fontovi */
    --font-heading: 'Cormorant Garamond', serif;
    --font-body: 'Barlow', sans-serif;
    --font-ui: 'Segoe UI', system-ui, sans-serif;
}

/* 2. PRIPREMA ZA BUDUĆE TEME (Može se aktivirati dodavanjem data-theme="light" na <html>) */
html[data-theme="light"] {
    --gold: #b8962e;
    --gold-dim: rgba(184, 150, 46, 0.1);
    
    --black: #f8fafc;
    --dark: #f1f5f9;
    --surface: #ffffff;
    --surface2: #f1f5f9;
    --surface3: #e2e8f0;
    
    --border: #cbd5e1;
    --border-light: rgba(0, 0, 0, 0.1);
    
    --text: #0f172a;
    --text-dim: #475569;
    --muted: #94a3b8;
}
"""
with open(os.path.join(CSS_DIR, 'global_themes.css'), 'w', encoding='utf-8') as f:
    f.write(global_css_content)


# 3. Backup starog kalkulatora
if os.path.exists(CALC_TEMPLATE):
    shutil.copy2(CALC_TEMPLATE, CALC_TEMPLATE + '.bak')


# 4. Novi, prevedeni Kalkulator koji koristi globalni CSS
calc_html_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Angebotsrechner – Visković Group</title>
    
    <link rel="stylesheet" href="/static/css/global_themes.css">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Barlow:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
    
    <style>
        /* Ovdje NEMA :root definicija boja! Koristimo globalne iz global_themes.css */
        
        * { box-sizing: border-box; }
        body { 
            margin: 0; 
            font-family: var(--font-body); 
            background: var(--black); 
            color: var(--text); 
            padding-bottom: 100px;
            -webkit-font-smoothing: antialiased;
        }

        /* Navigacija / Header */
        .header {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex; justify-content: space-between; align-items: center;
            position: sticky; top: 0; z-index: 100;
        }
        .header-brand {
            font-family: var(--font-heading);
            font-size: 1.5rem;
            color: var(--gold);
            text-decoration: none;
        }
        .header-nav a {
            color: var(--text-dim);
            text-decoration: none;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: color 0.2s;
        }
        .header-nav a:hover { color: var(--gold); }

        /* Uvodni tekst (Trust Builder) */
        .intro-section {
            max-width: 900px;
            margin: 40px auto 20px;
            padding: 0 24px;
            text-align: center;
        }
        .intro-title {
            font-family: var(--font-heading);
            font-size: 2.5rem;
            color: var(--white);
            margin-bottom: 16px;
            font-weight: 300;
        }
        .intro-title em { color: var(--gold); }
        .intro-text {
            color: var(--text-dim);
            font-size: 1.05rem;
            line-height: 1.6;
            margin-bottom: 30px;
        }

        /* Glavni kontejner */
        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 0 24px;
            display: grid;
            gap: 24px;
        }

        /* Kartice */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
        }
        .card-header {
            display: flex; align-items: center; gap: 12px;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-light);
        }
        .card-icon {
            width: 40px; height: 40px;
            background: var(--gold-dim);
            color: var(--gold);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
        }
        .card-title {
            font-family: var(--font-ui);
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text);
            margin: 0;
        }
        .card-desc {
            font-size: 0.8rem;
            color: var(--text-dim);
            margin-top: 4px;
        }

        /* Input polja i Gumbi */
        .form-group { margin-bottom: 16px; }
        .form-label {
            display: block; font-size: 0.85rem; color: var(--text-dim);
            margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;
        }
        .form-control {
            width: 100%; padding: 12px 16px;
            background: var(--surface3);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: 6px;
            font-family: var(--font-ui);
            font-size: 1rem;
            transition: border-color 0.2s;
        }
        .form-control:focus { outline: none; border-color: var(--gold); }
        
        .btn {
            padding: 12px 24px;
            border: none; border-radius: 6px;
            font-family: var(--font-body);
            font-weight: 600; font-size: 0.9rem;
            text-transform: uppercase; letter-spacing: 1px;
            cursor: pointer; transition: all 0.2s;
        }
        .btn-primary {
            background: var(--gold);
            color: var(--black);
            width: 100%;
        }
        .btn-primary:hover { background: var(--gold2); }
        .btn-outline {
            background: transparent;
            border: 1px dashed var(--gold-border);
            color: var(--gold);
        }
        .btn-outline:hover { background: var(--gold-dim); }

        /* Dinamički redovi (Tablice) */
        .item-row {
            display: grid; grid-template-columns: 2fr 1fr auto; gap: 12px;
            align-items: center; margin-bottom: 12px;
            background: var(--surface2); padding: 12px; border-radius: 6px;
        }
        .btn-remove {
            background: transparent; border: none;
            color: var(--red); cursor: pointer;
            padding: 8px; font-size: 1.1rem;
        }

        /* Rezultati */
        .result-box {
            background: var(--surface2);
            padding: 16px; border-radius: 6px;
            display: flex; justify-content: space-between; align-items: center;
            margin-top: 16px; border: 1px solid var(--border-light);
        }
        .result-label { font-size: 0.9rem; color: var(--text-dim); }
        .result-value { font-family: var(--font-ui); font-size: 1.25rem; font-weight: 700; color: var(--gold); }
        
        .grand-total {
            background: var(--gold-dim);
            border: 1px solid var(--gold-border);
            padding: 24px; text-align: center;
            border-radius: var(--radius);
        }
        .grand-total-label { color: var(--gold); font-size: 1rem; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }
        .grand-total-val { font-family: var(--font-heading); font-size: 3.5rem; color: var(--white); line-height: 1; }

        @media (max-width: 768px) {
            .item-row { grid-template-columns: 1fr; }
            .grand-total-val { font-size: 2.5rem; }
        }
    </style>
</head>
<body>

<div class="header">
    <a href="/" class="header-brand">VISKOVIĆ GROUP</a>
    <div class="header-nav"><a href="/"><i class="fas fa-arrow-left"></i> Zurück</a></div>
</div>

<div class="intro-section">
    <h1 class="intro-title">Open-Book <em>Kalkulation</em>.</h1>
    <p class="intro-text">
        Bei der Visković Group gibt es keine versteckten Kosten. Wir legen großen Wert auf vollständige Transparenz – von den direkten Arbeitskosten über die Materialbeschaffung bis hin zu unserer Unternehmensmarge. Berechnen Sie Ihr Projekt ehrlich und fair.
    </p>
</div>

<div class="container">
    
    <div class="card">
        <div class="card-header">
            <div class="card-icon"><i class="fas fa-hard-hat"></i></div>
            <div>
                <h2 class="card-title">1. Personalkosten</h2>
                <div class="card-desc">Berechnung der realen Stundenlöhne inkl. 17% Sozialabgaben und Transport.</div>
            </div>
        </div>
        
        <div id="workers-container">
            </div>
        <button class="btn btn-outline" onclick="addWorker()" style="width: 100%; margin-top: 10px;">
            <i class="fas fa-plus"></i> Mitarbeiter hinzufügen
        </button>
        
        <div class="result-box">
            <div class="result-label">Personalkosten (Gesamt/Tag):</div>
            <div class="result-value" id="total-workers-day">0,00 €</div>
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <div class="card-icon"><i class="fas fa-cubes"></i></div>
            <div>
                <h2 class="card-title">2. Material & Beschaffung</h2>
                <div class="card-desc">Notwendiges Baumaterial für Ihr Projekt.</div>
            </div>
        </div>
        
        <div id="material-container"></div>
        <button class="btn btn-outline" onclick="addMaterial()" style="width: 100%; margin-top: 10px;">
            <i class="fas fa-plus"></i> Materialposition hinzufügen
        </button>
        
        <div class="result-box">
            <div class="result-label">Materialkosten (Gesamt):</div>
            <div class="result-value" id="total-material">0,00 €</div>
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <div class="card-icon"><i class="fas fa-chart-pie"></i></div>
            <div>
                <h2 class="card-title">3. Unternehmensstruktur (Open-Book)</h2>
                <div class="card-desc">Offenlegung unserer Regiekosten und Gewinnmarge.</div>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div class="form-group">
                <label class="form-label">Regiekosten (%)</label>
                <input type="number" id="overhead-percent" class="form-control" value="15" onchange="calculateTotal()">
                <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 8px;">Fahrzeuge, Werkzeuge, Verwaltung</div>
            </div>
            <div class="form-group">
                <label class="form-label">Gewinnmarge (%)</label>
                <input type="number" id="profit-percent" class="form-control" value="20" onchange="calculateTotal()">
                <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 8px;">Projektmanagement & Ertrag</div>
            </div>
        </div>
    </div>

    <div class="grand-total">
        <div class="grand-total-label">Gesamtangebot (Netto)</div>
        <div class="grand-total-val" id="grand-total">0,00 €</div>
        <div style="color: var(--text-dim); margin-top: 16px; font-size: 0.9rem;">
            Zzgl. 19% MwSt. (DE) / 25% PDV (HR)<br>
            <em style="color: var(--gold); font-size: 0.8rem;">*Die Berechnung ist unverbindlich.</em>
        </div>
    </div>

</div>

<script>
    function formatCurrency(num) {
        return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(num);
    }

    // Dodavanje Radnika
    function addWorker() {
        const container = document.getElementById('workers-container');
        const id = Date.now();
        const html = `
            <div class="item-row" id="worker-${id}">
                <input type="text" class="form-control" placeholder="Bezeichnung (z.B. Fliesenleger)" value="Facharbeiter">
                <input type="number" class="form-control worker-wage" placeholder="Tageslohn (€)" value="150" oninput="calculateTotal()">
                <button class="btn-remove" onclick="document.getElementById('worker-${id}').remove(); calculateTotal();"><i class="fas fa-trash"></i></button>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
        calculateTotal();
    }

    // Dodavanje Materijala
    function addMaterial() {
        const container = document.getElementById('material-container');
        const id = Date.now();
        const html = `
            <div class="item-row" id="mat-${id}">
                <input type="text" class="form-control" placeholder="Materialbeschreibung">
                <input type="number" class="form-control mat-cost" placeholder="Kosten (€)" value="0" oninput="calculateTotal()">
                <button class="btn-remove" onclick="document.getElementById('mat-${id}').remove(); calculateTotal();"><i class="fas fa-trash"></i></button>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
        calculateTotal();
    }

    // Glavna kalkulacija
    function calculateTotal() {
        // 1. Zbroj radnika (dodajemo 17% za doprinose)
        let workersTotal = 0;
        document.querySelectorAll('.worker-wage').forEach(inp => {
            let wage = parseFloat(inp.value) || 0;
            workersTotal += wage * 1.17; // Brutto + 17%
        });
        document.getElementById('total-workers-day').textContent = formatCurrency(workersTotal);

        // 2. Zbroj materijala
        let matTotal = 0;
        document.querySelectorAll('.mat-cost').forEach(inp => {
            matTotal += parseFloat(inp.value) || 0;
        });
        document.getElementById('total-material').textContent = formatCurrency(matTotal);

        // 3. Režija i Profit
        let overheadPct = (parseFloat(document.getElementById('overhead-percent').value) || 0) / 100;
        let profitPct = (parseFloat(document.getElementById('profit-percent').value) || 0) / 100;

        let directCosts = workersTotal + matTotal;
        let withOverhead = directCosts * (1 + overheadPct);
        let finalNetto = withOverhead * (1 + profitPct);

        document.getElementById('grand-total').textContent = formatCurrency(finalNetto);
    }

    // Inicijalno dodaj po jedan prazan red
    window.onload = function() {
        addWorker();
        addMaterial();
    };
</script>

</body>
</html>
"""

with open(CALC_TEMPLATE, 'w', encoding='utf-8') as f:
    f.write(calc_html_content)

print("✅ USPJEH! Centralni CSS je kreiran. Kalkulator je redizajniran, preveden na njemački i ugrađen.")
