import os
import shutil

BASE_DIR = '/var/www/fina-connect'
PRAVI_CMS_HTML = os.path.join(BASE_DIR, 'templates/website/index.html')
SIDEBAR_HTML = os.path.join(BASE_DIR, 'templates/base.html')

print("⏳ 1/3 Backupiram točne datoteke...")
if os.path.exists(PRAVI_CMS_HTML):
    shutil.copy2(PRAVI_CMS_HTML, PRAVI_CMS_HTML + '.bak_final_cms')
if os.path.exists(SIDEBAR_HTML):
    shutil.copy2(SIDEBAR_HTML, SIDEBAR_HTML + '.bak_final_cms')

print("⏳ 2/3 Popravljam mrtvi link u bočnom izborniku (Sidebar)...")
with open(SIDEBAR_HTML, 'r', encoding='utf-8') as f:
    sidebar_code = f.read()

# Mijenjamo stari link u ispravni Django url tag
if 'href="/website/"' in sidebar_code:
    sidebar_code = sidebar_code.replace('href="/website/"', 'href="{% url \'website:admin_panel\' %}"')
    with open(SIDEBAR_HTML, 'w', encoding='utf-8') as f:
        f.write(sidebar_code)
    print("✅ Bočni izbornik je popravljen!")

print("⏳ 3/3 Generiram Enterprise Tamni Web CMS na pravoj lokaciji...")
enterprise_cms_html = """{% extends 'base.html' %}
{% load i18n %}

{% block title %}Web Portal CMS | Visković Group{% endblock %}
{% block page_title %}Zentrales Web Management{% endblock %}

{% block content %}
<style>
    /* ENTERPRISE DARK THEME ZA CMS */
    .cms-container { padding: 10px; }
    .cms-header { border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
    .cms-title { font-family: 'Barlow Condensed', sans-serif; font-size: 2.2rem; color: var(--gold); letter-spacing: 2px; text-transform: uppercase; margin: 0; }
    .cms-subtitle { color: var(--text-dim); font-size: 0.95rem; margin-top: 5px; }
    
    .cms-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }
    
    .cms-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; display: flex; flex-direction: column; transition: all 0.3s; position: relative; overflow: hidden; }
    .cms-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: var(--border); transition: all 0.3s; }
    .cms-card:hover { border-color: var(--gold-border); transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
    .cms-card:hover::before { background: var(--gold); }
    
    .cms-card-header { display: flex; align-items: center; gap: 15px; margin-bottom: 20px; }
    .cms-icon { width: 50px; height: 50px; border-radius: 10px; background: rgba(201, 168, 76, 0.1); color: var(--gold); display: flex; align-items: center; justify-content: center; font-size: 1.5rem; }
    .cms-card-title { font-size: 1.3rem; font-weight: 700; margin: 0; color: var(--text); }
    .cms-badge { background: #ef4444; color: white; padding: 4px 10px; border-radius: 99px; font-size: 0.75rem; font-weight: 800; margin-left: auto; animation: pulse-red 2s infinite; letter-spacing: 1px; }
    
    @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }
    
    .cms-btn { background: var(--surface2); color: var(--text); border: 1px solid var(--border); padding: 12px 15px; border-radius: 8px; text-decoration: none; font-weight: 600; text-align: center; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; margin-top: auto; letter-spacing: 1px; text-transform: uppercase; font-size: 0.85rem;}
    .cms-btn:hover { background: var(--gold); color: #000; border-color: var(--gold); }
    .cms-btn.primary { background: var(--gold); color: #000; border-color: var(--gold); }
    .cms-btn.primary:hover { background: var(--gold-dim); }
    .cms-btn:disabled { opacity: 0.7; cursor: not-allowed; }

    .preview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
    .preview-img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 6px; border: 1px solid var(--border); }
    
    .list-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px dashed var(--border); font-size: 0.9rem; }
    .list-item:last-child { border-bottom: none; }
</style>

<div class="cms-container">
    <div class="cms-header">
        <div>
            <h1 class="cms-title">Web Portal CMS</h1>
            <div class="cms-subtitle">Centralno zapovjedno mjesto za viskovic-group.de</div>
        </div>
        <a href="/" target="_blank" class="cms-btn" style="width: auto; padding: 10px 20px;"><i class="fas fa-external-link-alt"></i> Pregledaj Web</a>
    </div>

    <div class="cms-grid">
        <div class="cms-card">
            <div class="cms-card-header">
                <div class="cms-icon"><i class="fas fa-camera"></i></div>
                <h2 class="cms-card-title">Foto Galerija</h2>
            </div>
            <div class="preview-grid">
                {% for img in gallery|slice:":3" %}
                    <img src="{{ img.image.url }}" class="preview-img" alt="Referenca">
                {% empty %}
                    <div style="grid-column: 1/-1; color: var(--text-dim); text-align: center; padding: 20px 0;">
                        <i class="fas fa-image fa-2x mb-2" style="opacity: 0.2;"></i><br>Nema aktivnih slika
                    </div>
                {% endfor %}
            </div>
            <p style="color: var(--text-dim); font-size: 0.85rem; margin-bottom: 20px;">Ukupno aktivnih slika u sustavu: <strong>{{ gallery.count }}</strong></p>
            <a href="/admin/website/galleryimage/" class="cms-btn action-btn" onclick="pokreniLoading(this)">
                <i class="fas fa-images"></i> Upravljaj Galerijom
            </a>
        </div>

        <div class="cms-card">
            <div class="cms-card-header">
                <div class="cms-icon"><i class="fas fa-film"></i></div>
                <h2 class="cms-card-title">Video Reference</h2>
            </div>
            <div style="margin-bottom: 20px; color: var(--text-dim); font-size: 0.95rem; line-height: 1.6;">
                Upravljajte video zapisima s gradilišta i YouTube poveznicama koje se prikazuju na javnom portalu (BAU, Najam).
            </div>
            <a href="/admin/website/videogallery/" class="cms-btn action-btn" onclick="pokreniLoading(this)">
                <i class="fas fa-video"></i> Upravljaj Videima
            </a>
        </div>

        <div class="cms-card">
            <div class="cms-card-header">
                <div class="cms-icon" style="background: rgba(239, 68, 68, 0.1); color: #ef4444;"><i class="fas fa-truck-fast"></i></div>
                <h2 class="cms-card-title">Hitne Intervencije</h2>
                {% if hitne.count > 0 %}<div class="cms-badge">{{ hitne.count }} NOVIH</div>{% endif %}
            </div>
            <div style="margin-bottom: 20px;">
                {% for h in hitne|slice:":3" %}
                    <div class="list-item">
                        <span style="color: var(--text); font-weight: 600;">{{ h.ime }} <span style="color: var(--text-dim); font-size: 0.8rem; font-weight: normal;">({{ h.grad }})</span></span>
                        <span style="color: #ef4444; font-weight: 700; font-size: 0.75rem;"><i class="fas fa-circle" style="font-size: 6px; vertical-align: middle;"></i> NOVO</span>
                    </div>
                {% empty %}
                    <div style="color: var(--text-dim); text-align: center; padding: 20px 0;">
                        <i class="fas fa-check-circle fa-2x mb-2" style="color: #22c55e; opacity: 0.5;"></i><br>Svi zahtjevi su obrađeni
                    </div>
                {% endfor %}
            </div>
            <a href="/admin/website/hitnaintervencija/" class="cms-btn primary action-btn" onclick="pokreniLoading(this)">
                <i class="fas fa-inbox"></i> Otvori SOS Prijemnik
            </a>
        </div>

        <div class="cms-card">
            <div class="cms-card-header">
                <div class="cms-icon"><i class="fas fa-tags"></i></div>
                <h2 class="cms-card-title">Partneri & Brendovi</h2>
            </div>
            <div style="margin-bottom: 20px;">
                {% for b in brands|slice:":3" %}
                    <div class="list-item">
                        <span><span style="display:inline-block; width:20px; text-align:center; color:var(--gold);">{{ b.icon|safe }}</span> {{ b.name }}</span>
                        <i class="fas fa-check" style="color: #22c55e;"></i>
                    </div>
                {% empty %}
                    <div style="color: var(--text-dim); text-align: center; padding: 20px 0;">Nema dodanih brendova</div>
                {% endfor %}
            </div>
            <a href="/admin/website/brand/" class="cms-btn action-btn" onclick="pokreniLoading(this)">
                <i class="fas fa-edit"></i> Uredi Brendove
            </a>
        </div>
    </div>
</div>

<script>
    function pokreniLoading(button) {
        if (button.classList.contains('disabled')) return false;
        
        const originalText = button.innerHTML;
        button.classList.add('disabled');
        button.style.pointerEvents = 'none';
        button.style.opacity = '0.7';
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Otvaranje Modula...';
        
        setTimeout(() => {
            button.classList.remove('disabled');
            button.style.pointerEvents = 'auto';
            button.style.opacity = '1';
            button.innerHTML = originalText;
        }, 4000);
    }
</script>
{% endblock %}
"""

with open(PRAVI_CMS_HTML, 'w', encoding='utf-8') as f:
    f.write(enterprise_cms_html)

os.system("supervisorctl restart fina-connect")
print("✅ SVE ZAVRŠENO U JEDNOM KORAKU! Bočni izbornik i CMS su spremni.")
