"""
Mobile Polish + Design System injection — top dashboards
Dodaje responsive CSS na sve dashboarde koji ga nemaju.
"""
import os
import re
BASE = '/var/www/fina-connect/templates'

MOBILE_CSS = """
<style>
@media(max-width:768px){
  .container-fluid{padding-left:.5rem;padding-right:.5rem}
  .table-responsive{font-size:.78rem}
  .table th,.table td{padding:.4rem .5rem}
  .btn-sm{font-size:.7rem;padding:3px 8px}
  .row.g-2>div,.row.g-3>div{flex:0 0 100%;max-width:100%}
  .stat-card,.card{margin-bottom:.5rem}
  h2,.h2{font-size:1.2rem}
  h4,.h4{font-size:1rem}
  .d-flex.justify-content-between{flex-wrap:wrap;gap:.5rem}
}
@media(max-width:480px){
  .table th:nth-child(n+5),.table td:nth-child(n+5){display:none}
  .btn{font-size:.75rem}
  .stat-card .fs-4,.stat-mini .val,.exp-stat-value,.flock-stat-value{font-size:1.2rem}
}
</style>
"""

# Nađi sve dashboarde i liste bez @media
count = 0
for root, dirs, files in os.walk(BASE):
    # Skip experiences (already done) and backup files
    if 'experiences' in root:
        continue
    for fname in files:
        if not fname.endswith('.html'):
            continue
        if '.bak' in fname:
            continue
        path = os.path.join(root, fname)
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Samo fajlovi koji extend base.html i imaju tablice ili stat kartice
        if '{% extends' not in content:
            continue
        if '@media' in content:
            continue
        
        # Samo dashboardi, liste i forme
        is_target = any(x in fname for x in ['dashboard', 'list', 'kanban', 'board', 'detail', 'form'])
        if not is_target:
            continue
        
        # Inject mobile CSS
        if '{% block extra_css %}' in content:
            content = content.replace(
                '{% block extra_css %}',
                '{% block extra_css %}' + MOBILE_CSS
            )
        elif '{% block content %}' in content:
            content = content.replace(
                '{% block content %}',
                '{% block extra_css %}' + MOBILE_CSS + '{% endblock %}\n{% block content %}'
            )
        else:
            continue
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        rel = os.path.relpath(path, BASE)
        count += 1

print(f"[OK] {count} templatea dobilo mobile responsive CSS")
