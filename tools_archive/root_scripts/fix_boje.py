import os

CSS_FILE = '/var/www/fina-connect/static/css/global_themes.css'
BAU_FILE = '/var/www/fina-connect/website/templates/website/bau.html'

# 1. Popravak global_themes.css (Dodavanje --white varijable)
if os.path.exists(CSS_FILE):
    with open(CSS_FILE, 'r', encoding='utf-8') as f:
        css_content = f.read()
        
    if '--white:' not in css_content:
        # Dodajemo --white odmah ispod --black
        css_content = css_content.replace('--black: #0a0a0a;', '--black: #0a0a0a;\n    --white: #f0ede8;')
        with open(CSS_FILE, 'w', encoding='utf-8') as f:
            f.write(css_content)

# 2. Popravak bau.html (Koristimo var(--text) koji je pouzdaniji i definiran)
if os.path.exists(BAU_FILE):
    with open(BAU_FILE, 'r', encoding='utf-8') as f:
        bau_content = f.read()
        
    # Mijenjamo sporno pozivanje nepostojeće varijable u ispravnu
    bau_content = bau_content.replace('var(--white)', 'var(--text)')
    
    with open(BAU_FILE, 'w', encoding='utf-8') as f:
        f.write(bau_content)

print("✅ BOJE SU POPRAVLJENE! Varijabla je dodana i naslovi će sada biti svijetli.")
