#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

TARGET_FILE = Path('/var/www/fina-connect/premium_booking/templates/premium_booking/index.html')

print("🛠️ Rješavanje odrezanog izbornika i integracija mobilnog sučelja...")

if TARGET_FILE.exists():
    content = TARGET_FILE.read_text(encoding='utf-8')
    
    # 1. Popravak 'odrezanog' ekrana (globalni box-sizing)
    if 'box-sizing: border-box;' not in content:
        content = content.replace(
            ':root {',
            '*, *::before, *::after { box-sizing: border-box; }\n        :root {'
        )
    
    # 2. Dodavanje responzivnosti (Media Queries za mobitele i male ekrane)
    if '@media (max-width: 768px)' not in content:
        mobile_css = """
        /* ── MOBILNA PRILAGODBA ── */
        @media (max-width: 768px) {
            header { padding: 15px 20px; flex-direction: column; gap: 15px; }
            .logo { font-size: 1.5rem; letter-spacing: 2px; }
            .lang-switcher { margin-left: 0; justify-content: center; width: 100%; flex-wrap: wrap; }
            
            .hero { height: 40vh; }
            .hero h1 { font-size: 2.5rem; letter-spacing: 4px; }
            .hero p { font-size: 0.65rem !important; letter-spacing: 4px !important; padding: 0 10px; }
            
            .grid { padding: 40px 20px; grid-template-columns: 1fr; gap: 30px; }
            .res-content { padding: 30px; }
            .res-content h2 { font-size: 2.2rem !important; margin: 15px 0 !important; }
            .btn-vg { padding: 15px 20px; font-size: 0.8rem; }
        }
    </style>"""
        content = content.replace('</style>', mobile_css)
        
    TARGET_FILE.write_text(content, encoding='utf-8')
    print(f"✅ Uspješno popravljen CSS i ubačen mobilni dizajn: {TARGET_FILE.name}")
else:
    print(f"❌ GREŠKA: Ne mogu pronaći datoteku {TARGET_FILE}")

print("🔄 Restartam server...")
os.system("supervisorctl restart fina-connect")
print("✨ GOTOVO! Osvježi Premium stranicu na računalu i provjeri na mobitelu.")
