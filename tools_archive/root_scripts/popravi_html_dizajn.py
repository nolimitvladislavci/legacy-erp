import os

BAU_HTML = '/var/www/fina-connect/website/templates/website/bau.html'

print("⏳ Prisilno mijenjam HTML predložak za galeriju...")

with open(BAU_HTML, 'r', encoding='utf-8') as f:
    html = f.read()

# Tražimo točne koordinate stare galerije
start_idx = html.find('<div class="gallery-grid">')
end_idx = html.find('</section>', start_idx)

if start_idx != -1 and end_idx != -1:
    new_grid = """<div class="gallery-grid">
        {% if media_items %}
            {% for item in media_items %}
            <div class="gallery-item">
                {% if item.type == 'image' %}
                    <img src="{{ item.url }}" alt="{{ item.title }}">
                {% elif item.type == 'video_file' %}
                    <video width="100%" height="100%" style="object-fit: cover; background: #000;" controls muted playsinline preload="metadata">
                        <source src="{{ item.url }}" type="video/mp4">
                    </video>
                {% elif item.type == 'video_embed' %}
                    <iframe src="{{ item.url }}" width="100%" height="100%" style="border:none;" allowfullscreen></iframe>
                {% endif %}
                
                <div class="gallery-overlay" style="pointer-events: none;">
                    <div class="gallery-title">{{ item.title }}</div>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div style="grid-column: 1 / -1; text-align: center; color: var(--gold); padding: 60px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px;">
                <i class="fas fa-exclamation-triangle fa-2x" style="margin-bottom: 15px;"></i>
                <h3 style="font-family: 'Barlow Condensed'; letter-spacing: 2px; text-transform: uppercase;">Veza prekinuta</h3>
                <p style="color: var(--text-dim);">Dizajn je ažuriran, ali Backend i dalje ne šalje slike iz baze. Pošaljite ovo Geminiju.</p>
            </div>
        {% endif %}
    </div>\n"""
    
    # Kirurški spajamo novi kod u sredinu datoteke
    nova_skripta = html[:start_idx] + new_grid + html[end_idx:]
    
    with open(BAU_HTML, 'w', encoding='utf-8') as f:
        f.write(nova_skripta)
        
    print("✅ HTML DIZAJN JE USPJEŠNO PREPISAN!")
else:
    print("❌ GREŠKA: Nisam mogao pronaći grid u HTML datoteci.")
