import os
import shutil
import re

FILE_PATH = '/var/www/fina-connect/templates/dashboards/superadmin.html'

print("⏳ 1/2 Radim sigurnosni backup Superadmin dashboarda...")
if os.path.exists(FILE_PATH):
    shutil.copy2(FILE_PATH, FILE_PATH + '.bak_cms_link2')

print("⏳ 2/2 Ugrađujem CMS karticu u grid...")
with open(FILE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Kirurški precizan Regex koji hvata cijeli Django Admin a-tag neovisno o razmacima
pattern = re.compile(r'(<a href="/admin/" class="action-card" target="_blank">.*?</a>)', re.DOTALL)

nova_kartica = """
        <a href="{% url 'website:admin_panel' %}" class="action-card" onclick="this.style.pointerEvents='none'; this.style.opacity='0.6'; this.querySelector('.fa-globe').className='fas fa-spinner fa-spin';">
            <i style="background:rgba(201,168,76,.15);color:#c9a84c"><i class="fas fa-globe"></i></i>
            <div>{% trans "Web Portal CMS" %}<div class="desc">{% trans "Javni web, galerija, SOS" %}</div></div>
        </a>"""

if pattern.search(content):
    content = pattern.sub(r'\1' + nova_kartica, content, count=1)
    
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ USPJEH! CMS kartica je savršeno integrirana u vaš grid.")
else:
    print("❌ GREŠKA: Nisam mogao locirati Django Admin karticu.")

os.system("supervisorctl restart fina-connect")
