import os
import re

VIEWS_FILE = '/var/www/fina-connect/core/views.py'
TPL_FILE = '/var/www/fina-connect/templates/dashboards/partner.html'

print("⏳ 1/2 Spajam bazu slika sa Staklenom sobom (views.py)...")
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_code = f.read()

# Ubacujemo logiku za povlačenje ProjectPhoto modela
if "site_photos = ProjectPhoto.objects" not in views_code:
    # Nalazimo gdje se povlače time_entries i dodajemo slike odmah ispod
    views_code = views_code.replace(
        "time_entries = TimeEntry.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-date', '-start_time')[:15]",
        "time_entries = TimeEntry.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-date', '-start_time')[:15]\n        \n        from worktime.models import ProjectPhoto\n        site_photos = ProjectPhoto.objects.filter(project_lead__in=my_leads).select_related('user').order_by('-created_at')[:8]"
    )
    
    # Dodajemo default varijablu izvan try bloka da ne puca
    views_code = views_code.replace(
        "time_entries = []",
        "time_entries = []\n    site_photos = []"
    )
    
    # Proslijeđujemo varijablu u HTML
    views_code = views_code.replace(
        "'time_entries': time_entries,",
        "'time_entries': time_entries,\n        'site_photos': site_photos,"
    )

with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(views_code)


print("⏳ 2/2 Ažuriram Dizajn Staklene sobe (partner.html)...")
with open(TPL_FILE, 'r', encoding='utf-8') as f:
    html = f.read()

foto_sekcija = """
            </div> <div class="section-box" style="margin-top: 24px;">
                <div class="box-header">
                    <h2 class="box-title"><i class="fas fa-camera"></i> Live Bilder vom Bauprojekt</h2>
                    <span style="font-size: 0.7rem; color: var(--text-dim); border: 1px solid var(--border); padding: 4px 8px; border-radius: 4px;">Zuletzt aktualisiert: Heute</span>
                </div>
                
                <div style="padding: 24px;">
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px;">
                        {% if site_photos %}
                            {% for foto in site_photos %}
                            <div style="border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface2);">
                                <div style="aspect-ratio: 1; overflow: hidden; position: relative;">
                                    <a href="{{ foto.image.url }}" target="_blank">
                                        <img src="{{ foto.image.url }}" style="width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s;" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
                                    </a>
                                </div>
                                <div style="padding: 12px; font-size: 0.75rem;">
                                    <div style="color: var(--gold); font-weight: 700; margin-bottom: 4px;">{{ foto.created_at|date:"d.m.Y H:i" }}</div>
                                    <div style="color: var(--text);"><i class="fas fa-hard-hat" style="color: var(--text-dim);"></i> {{ foto.user.first_name|default:foto.user.username }}</div>
                                    {% if foto.note %}
                                    <div style="color: var(--text-dim); margin-top: 6px; font-style: italic;">"{{ foto.note }}"</div>
                                    {% endif %}
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <div style="grid-column: 1 / -1; text-align: center; color: var(--text-dim); padding: 20px 0;">
                                <i class="fas fa-image fa-2x" style="opacity: 0.2; margin-bottom: 10px;"></i>
                                <p>Noch keine Fotos vom Projekt hochgeladen.</p>
                            </div>
                        {% endif %}
                    </div>
                </div>
"""

# Ubacujemo ovu sekciju točno ispod tablice s radnim satima
if "Live Bilder vom Bauprojekt" not in html:
    html = html.replace(
        'Alle Einträge anzeigen ↓</a>\n                </div>\n            </div>',
        'Alle Einträge anzeigen ↓</a>\n                </div>\n' + foto_sekcija + '\n            </div>'
    )

with open(TPL_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

os.system("supervisorctl restart fina-connect")
print("✅ GOTOVO! Klijent sada vidi slike u svom Dashboardu!")
