#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

TARGET_FILES = [
    Path('/var/www/fina-connect/website/templates/website/homepage.html'),
    Path('/var/www/fina-connect/templates/viskovic_group_index.html')
]

print("🛠️ Integracija mobilnog dizajna i centriranje jezika na glavnoj naslovnici...")

mobile_css = """
        /* ── KOREKCIJA MOBILNOG ZAGLAVLJA I JEZIKA (NASLOVNICA) ── */
        @media (max-width: 900px) {
            header#header { 
                padding: 15px 20px !important; 
                flex-direction: column !important; 
                height: auto !important; 
                gap: 15px !important; 
                background: rgba(10,10,10,0.98) !important;
            }
            header#header nav { 
                width: 100% !important; 
                justify-content: center !important; 
                flex-wrap: wrap !important; 
                gap: 10px !important; 
            }
            /* Sakrivanje tekstualnih linkova na mobitelu zbog prostora */
            header#header nav > a { display: none !important; }
            
            /* Prikazivanje samo ključnih gumba */
            header#header nav > a.nav-erp, header#header nav > a.btn-primary { 
                display: inline-block !important; 
                font-size: 0.75rem !important;
                padding: 10px 16px !important;
                text-align: center;
            }
            
            /* Oslobađanje jezika iz okvira i centriranje na vrh navigacije */
            .lang-switcher { 
                width: 100% !important; 
                justify-content: center !important; 
                margin: 5px 0 10px 0 !important; 
                border: none !important; 
                padding: 0 !important; 
                order: -1; /* Prikaz jezika iznad gumba na mobitelu */
            }
            .lang-switcher form { flex-wrap: wrap; justify-content: center; }
        }
    </style>"""

for file_path in TARGET_FILES:
    if file_path.exists():
        content = file_path.read_text(encoding='utf-8')
        
        # Osiguranje da ne upisujemo dupli kod
        if 'KOREKCIJA MOBILNOG ZAGLAVLJA I JEZIKA' not in content:
            content = content.replace('</style>', mobile_css)
            file_path.write_text(content, encoding='utf-8')
            print(f"✅ Mobilni dizajn uspješno ubačen u: {file_path.name}")
        else:
            print(f"ℹ️ Mobilni dizajn već postoji u {file_path.name}")

print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")
print("✨ GOTOVO! Osvježi crnu naslovnicu (viskovic-group.de) na mobitelu.")
