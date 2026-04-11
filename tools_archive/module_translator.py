import os
import shutil

print("🚀 Integracija 'Modul po modul' arhitekture prevoditelja...")

views_path = 'accounts/views.py'
template_path = 'accounts/templates/accounts/translation_manager.html'

# 1. KREIRANJE BACKUPA PREMA PRAVILIMA
if os.path.exists(views_path):
    shutil.copy2(views_path, f"{views_path}.bak")
if os.path.exists(template_path):
    shutil.copy2(template_path, f"{template_path}.bak")
print("📦 Kreirani sigurnosni .bak backupi.")

# 2. INJEKCIJA NOVE PYTHON LOGIKE (ZAMJENA ZADNJE FUNKCIJE)
with open(views_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_logic = """@login_required
@user_passes_test(lambda u: u.is_superuser)
def translation_manager(request, lang_code='de'):
    import polib
    import os
    from django.conf import settings
    
    po_path = os.path.join(settings.BASE_DIR, 'locale', lang_code, 'LC_MESSAGES', 'django.po')
    
    if not os.path.exists(po_path):
        messages.warning(request, f'Pojmovi su u bazi već na Hrvatskom. Preusmjereno na Njemački rječnik.')
        return redirect('accounts:translation_manager', lang_code='de')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'scan':
            os.system(f"cd {settings.BASE_DIR} && {settings.BASE_DIR}/venv/bin/python manage.py makemessages -l {lang_code} -e html,py --no-wrap")
            messages.success(request, f'✅ Portal skeniran. Baza riječi za {lang_code.upper()} je ažurirana.')
            return redirect('accounts:translation_manager', lang_code=lang_code)
            
        elif action == 'auto_translate_module':
            target_module = request.POST.get('target_module', 'ALL')
            try:
                from deep_translator import GoogleTranslator
                po = polib.pofile(po_path)
                translator = GoogleTranslator(source='hr', target=lang_code)
                count = 0
                for entry in po:
                    if not entry.msgstr and entry.msgid:
                        # Ako prevodimo specifični modul, preskoči riječi iz drugih modula
                        if target_module != 'ALL':
                            belongs = False
                            for occ in entry.occurrences:
                                path = occ[0].replace('\\\\', '/')
                                if path.startswith(target_module + '/'):
                                    belongs = True
                                    break
                            if not belongs:
                                continue
                                
                        try:
                            entry.msgstr = translator.translate(entry.msgid)
                            count += 1
                        except Exception:
                            pass
                po.save()
                os.system(f"cd {settings.BASE_DIR} && {settings.BASE_DIR}/venv/bin/python manage.py compilemessages")
                if target_module == 'ALL':
                    messages.success(request, f'✨ Uspješno prevedeno {count} pojmova u cijelom sustavu.')
                else:
                    messages.success(request, f'✨ Uspješno prevedeno {count} pojmova u modulu: {target_module.upper()}.')
            except Exception as e:
                messages.error(request, _('Nešto je pošlo krivo. Pokušajte ponovo ili kontaktirajte podršku.'))
            return redirect('accounts:translation_manager', lang_code=lang_code)
            
        else:
            msgid = request.POST.get('msgid')
            msgstr = request.POST.get('msgstr')
            if msgid:
                po = polib.pofile(po_path)
                entry = po.find(msgid)
                if entry:
                    entry.msgstr = msgstr
                    po.save()
                    os.system(f"cd {settings.BASE_DIR} && {settings.BASE_DIR}/venv/bin/python manage.py compilemessages")
                    messages.success(request, f'Prijevod za "{msgid}" spremljen.')
            return redirect('accounts:translation_manager', lang_code=lang_code)

    po = polib.pofile(po_path)
    entries = []
    modules_set = set()
    
    for e in po:
        if e.msgid:
            # Utvrđivanje modula iz putanje datoteke
            mod_name = 'ostalo'
            if e.occurrences:
                path = e.occurrences[0][0].replace('\\\\', '/')
                mod_name = path.split('/')[0]
            e.module_name = mod_name
            modules_set.add(mod_name)
            entries.append(e)
            
    return render(request, 'accounts/translation_manager.html', {
        'entries': entries,
        'modules': sorted(list(modules_set)),
        'lang_code': lang_code,
        'languages': ['de', 'en']
    })
"""

# Prerežemo točno tamo gdje počinje definicija funkcije
parts = content.split('@login_required\n@user_passes_test(lambda u: u.is_superuser)\ndef translation_manager')
if len(parts) == 2:
    with open(views_path, 'w', encoding='utf-8') as f:
        f.write(parts[0] + new_logic)
    print("✅ Python logika (Backend) uspješno usklađena.")
else:
    print("❌ Greška pri pronalasku funkcije u views.py.")

# 3. KREIRANJE NOVOG HTML-A S FILTRIMA I GUMBIMA
html_content = """{% extends "base.html" %}
{% block content %}
<div class="stat-card">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>🌍 Prevoditelj: {{ lang_code|upper }}</h2>
        <div class="btn-group">
            <a href="?lang_code=de" class="btn btn-outline-primary {% if lang_code == 'de' %}active{% endif %}">Njemački</a>
            <a href="?lang_code=en" class="btn btn-outline-primary {% if lang_code == 'en' %}active{% endif %}">Engleski</a>
        </div>
    </div>

    <div class="card bg-white mb-4 border-0 shadow-sm" style="border-radius: 12px; border: 1px solid #e2e8f0 !important;">
        <div class="card-body d-flex flex-wrap gap-3 align-items-center">
            <form method="post" class="m-0">
                {% csrf_token %}
                <button type="submit" name="action" value="scan" class="btn btn-outline-primary" style="font-weight: 600;" onclick="this.innerHTML='<i class=\\'fas fa-spinner fa-spin me-1\\'></i> Skeniram...';">
                    <i class="fas fa-search me-1"></i> 1. Skeniraj kod
                </button>
            </form>
            
            <div class="d-flex align-items-center gap-2 ms-md-4 p-2 bg-light rounded border">
                <i class="fas fa-filter text-muted ms-2"></i>
                <select id="moduleSelect" class="form-select form-select-sm border-0 bg-transparent" style="width: 160px; font-weight: bold; cursor: pointer;">
                    <option value="ALL">Svi moduli (Rizično)</option>
                    {% for mod in modules %}
                    <option value="{{ mod }}">{{ mod|upper }}</option>
                    {% endfor %}
                </select>
                
                <form method="post" class="m-0" id="autoTranslateForm">
                    {% csrf_token %}
                    <input type="hidden" name="target_module" id="targetModuleInput" value="ALL">
                    <button type="submit" name="action" value="auto_translate_module" class="btn btn-warning btn-sm" style="font-weight: 600;" onclick="this.innerHTML='<i class=\\'fas fa-spinner fa-spin me-1\\'></i> Prevodim...';">
                        <i class="fas fa-magic me-1"></i> 2. Prevedi odabrano
                    </button>
                </form>
            </div>
            
            <small class="text-muted ms-auto mt-2 mt-md-0" style="font-size: 0.75rem;">
                Odaberi pojedinačni modul (npr. invoicing) da smanjiš opterećenje na server.
            </small>
        </div>
    </div>

    <input type="text" id="translationSearch" class="form-control mb-3" placeholder="Pretraži pojmove unutar odabranog modula...">

    <div class="table-responsive">
        <table class="table table-hover">
            <thead class="table-light">
                <tr>
                    <th style="width: 45%;">Original (HR)</th>
                    <th style="width: 45%;">Prijevod ({{ lang_code|upper }})</th>
                    <th>Akcija</th>
                </tr>
            </thead>
            <tbody id="translationTable">
                {% for entry in entries %}
                <tr class="translation-row" data-module="{{ entry.module_name }}">
                    <form method="post">
                        {% csrf_token %}
                        <td>
                            <span class="badge bg-secondary mb-1" style="font-size: 0.6rem;">{{ entry.module_name|upper }}</span>
                            <small class="text-muted d-block" style="font-size: 0.7rem;">{{ entry.occurrences.0.0 }}</small>
                            <strong>{{ entry.msgid }}</strong>
                            <input type="hidden" name="msgid" value="{{ entry.msgid }}">
                        </td>
                        <td>
                            <textarea name="msgstr" class="form-control form-control-sm" rows="1">{{ entry.msgstr }}</textarea>
                        </td>
                        <td>
                            <button type="submit" class="btn btn-success btn-sm">Spremi</button>
                        </td>
                    </form>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<script>
document.getElementById('moduleSelect').addEventListener('change', function() {
    let selected = this.value;
    document.getElementById('targetModuleInput').value = selected;
    
    let rows = document.querySelectorAll('.translation-row');
    rows.forEach(row => {
        if (selected === 'ALL' || row.getAttribute('data-module') === selected) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    document.getElementById('translationSearch').value = '';
});

document.getElementById('translationSearch').addEventListener('keyup', function() {
    let filter = this.value.toLowerCase();
    let selectedModule = document.getElementById('moduleSelect').value;
    let rows = document.querySelectorAll('.translation-row');
    
    rows.forEach(row => {
        let text = row.innerText.toLowerCase();
        let matchesModule = (selectedModule === 'ALL' || row.getAttribute('data-module') === selectedModule);
        let matchesText = text.includes(filter);
        row.style.display = (matchesModule && matchesText) ? '' : 'none';
    });
});
</script>
{% endblock %}
"""

with open(template_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print("✅ Predložak (Frontend) usklađen. Moduli implementirani.")

# 4. OSIGURANJE DOZVOLA I RESTART
os.system("chown -R www-data:www-data /var/www/fina-connect/locale")
os.system("chown -R www-data:www-data /var/www/fina-connect/accounts")
os.system("supervisorctl restart fina-connect")

print("✨ Sustav osvježen. Upravljačka ploča prevoditelja spremna za test.")
