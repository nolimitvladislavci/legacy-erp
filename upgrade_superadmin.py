import os
import shutil
import subprocess
import sys
import textwrap


def print_status(msg):
    print(f"[+] {msg}")


app_dir = "superadmin_ai"

if not os.path.exists(app_dir):
    print("[-] GREŠKA: Modul 'superadmin_ai' ne postoji u root direktoriju. Provjeri točan naziv modula.")
    sys.exit(1)

# 1. Kreiranje backupa postojećih datoteka
print_status("Kreiram sigurnosne .bak kopije za views.py i dashboard.html...")
views_path = os.path.join(app_dir, "views.py")
if os.path.exists(views_path):
    shutil.copy2(views_path, f"{views_path}.bak_upgrade")

templates_dir = os.path.join(app_dir, "templates", "superadmin_ai")
os.makedirs(templates_dir, exist_ok=True)
dashboard_path = os.path.join(templates_dir, "dashboard.html")
if os.path.exists(dashboard_path):
    shutil.copy2(dashboard_path, f"{dashboard_path}.bak_upgrade")

# 2. Generiranje Premium Frontenda (Bez skraćivanja koda, potpuni feedback sustav)
print_status("Generiram potpuni Premium UI sa strogim loading i error handling sustavom...")

html_content = r"""<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Nadzorni Centar | Visković Group Premium</title>
    <style>
        :root {
            --bg-main: #0a0a0a;
            --bg-card: #151515;
            --gold-primary: #d4af37;
            --gold-hover: #b5952f;
            --text-main: #e0e0e0;
            --text-muted: #888888;
            --danger: #ff4444;
            --success: #00C851;
            --border-color: #333333;
        }
        body {
            background-color: var(--bg-main);
            color: var(--text-main);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        .header {
            border-bottom: 2px solid var(--gold-primary);
            padding-bottom: 15px;
            margin-bottom: 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            color: var(--gold-primary);
            font-weight: 300;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 0;
        }
        .card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8);
        }
        .card-title {
            color: var(--gold-primary);
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 1.2rem;
            text-transform: uppercase;
            border-bottom: 1px dashed var(--border-color);
            padding-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        th {
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85rem;
        }
        tr:hover td {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .module-name {
            font-weight: 600;
            color: #fff;
        }
        
        .premium-switch {
            position: relative;
            display: inline-block;
            width: 46px;
            height: 24px;
        }
        .premium-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: #2a2a2a;
            transition: .4s;
            border-radius: 24px;
            border: 1px solid #444;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 16px; width: 16px;
            left: 3px; bottom: 3px;
            background-color: #888;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: rgba(212, 175, 55, 0.2);
            border-color: var(--gold-primary);
        }
        input:checked + .slider:before {
            transform: translateX(22px);
            background-color: var(--gold-primary);
        }
        input:disabled + .slider {
            opacity: 0.4;
            cursor: not-allowed;
        }

        .btn {
            background: transparent;
            border: 1px solid var(--gold-primary);
            color: var(--gold-primary);
            padding: 8px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 140px;
        }
        .btn:hover:not(:disabled) {
            background: var(--gold-primary);
            color: var(--bg-main);
        }
        .btn-danger {
            border-color: var(--danger);
            color: var(--danger);
        }
        .btn-danger:hover:not(:disabled) {
            background: var(--danger);
            color: #fff;
        }
        .btn:disabled {
            border-color: #555;
            color: #555;
            cursor: not-allowed;
        }
        
        .code-block {
            background: #0d0d0d;
            border-left: 3px solid var(--gold-primary);
            padding: 15px;
            font-family: 'Courier New', Courier, monospace;
            color: #a3d9a5;
            font-size: 0.85rem;
            white-space: pre-wrap;
            margin-top: 10px;
        }

        #toast-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .toast {
            padding: 15px 25px;
            border-radius: 4px;
            color: #fff;
            background: var(--bg-card);
            border-left: 4px solid #fff;
            box-shadow: 0 4px 20px rgba(0,0,0,0.9);
            display: flex;
            align-items: center;
            gap: 15px;
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        }
        .toast.show {
            opacity: 1;
            transform: translateX(0);
        }
        .toast-success { border-color: var(--success); }
        .toast-error { border-color: var(--danger); }
        
        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: currentColor;
            animation: spin 1s ease-in-out infinite;
            margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Ovlasti Sustava</h1>
            <span style="color: var(--text-muted);">Kontrolni centar autonomije agenata</span>
        </div>

        <div class="card">
            <h2 class="card-title">Konfiguracija Pristupa po Modulima</h2>
            <table>
                <thead>
                    <tr>
                        <th>Modul</th>
                        <th style="text-align: center;">Čitanje (Read)</th>
                        <th style="text-align: center;">Pisanje (Write)</th>
                        <th style="text-align: center;">Kreiranje (Create)</th>
                        <th style="text-align: center;">Izmjene (Modify)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for m in modules %}
                    <tr>
                        <td class="module-name">{{ m.module_name }}</td>
                        <td style="text-align: center;">
                            <label class="premium-switch">
                                <input type="checkbox" onchange="togglePermission(this, {{ m.id }}, 'read')" {% if m.can_read %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                        </td>
                        <td style="text-align: center;">
                            <label class="premium-switch">
                                <input type="checkbox" onchange="togglePermission(this, {{ m.id }}, 'write')" {% if m.can_write %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                        </td>
                        <td style="text-align: center;">
                            <label class="premium-switch">
                                <input type="checkbox" onchange="togglePermission(this, {{ m.id }}, 'create')" {% if m.can_create %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                        </td>
                        <td style="text-align: center;">
                            <label class="premium-switch">
                                <input type="checkbox" onchange="togglePermission(this, {{ m.id }}, 'modify')" {% if m.can_modify %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2 class="card-title">AI Prijedlozi i Akcije na Čekanju</h2>
            <div id="actions-container">
                {% if actions %}
                    {% for a in actions %}
                    <div class="card" style="background-color: #111; margin-bottom: 20px; border-color: #222;" id="action-row-{{ a.id }}">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="color: var(--gold-primary); font-size: 1.1rem;">{{ a.module.module_name }} - {{ a.action_type }}</strong>
                            <span style="color: var(--text-muted); font-size: 0.8rem;">{{ a.created_at|date:"d.m.Y H:i" }}</span>
                        </div>
                        <p style="margin-top: 10px; line-height: 1.5;">{{ a.description }}</p>
                        {% if a.proposed_code %}
                            <div class="code-block">{{ a.proposed_code }}</div>
                        {% endif %}
                        <div style="margin-top: 20px; display: flex; gap: 15px;">
                            <button class="btn" onclick="resolveAction(this, {{ a.id }}, 'APPROVED')">Potvrdi Akciju</button>
                            <button class="btn btn-danger" onclick="resolveAction(this, {{ a.id }}, 'REJECTED')">Odbij</button>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <p style="color: var(--text-muted); text-align: center; padding: 20px;">Nema aktivnih prijedloga od strane AI agenata.</p>
                {% endif %}
            </div>
        </div>
    </div>

    <div id="toast-container"></div>

    <script>
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        function showToast(type, message) {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast toast-' + type;
            
            const icon = type === 'success' ? '✓' : '❌';
            toast.innerHTML = '<span style="font-weight: bold; font-size: 1.2rem;">' + icon + '</span> <span>' + message + '</span>';
            
            container.appendChild(toast);
            
            void toast.offsetWidth;
            toast.classList.add('show');
            
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => container.removeChild(toast), 400);
            }, 5000);
        }

        function togglePermission(element, moduleId, permType) {
            const originalState = !element.checked;
            const newState = element.checked;
            element.disabled = true;
            
            fetch('/superadmin-ai/api/update-permission/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    module_id: moduleId,
                    permission_type: permType,
                    value: newState
                })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                        throw new Error(errData.message || 'Greška servera kod spremanja dozvole.');
                    });
                }
                return response.json();
            })
            .then(res => {
                showToast('success', res.message || 'Dozvole su uspješno ažurirane.');
            })
            .catch(error => {
                showToast('error', error.message);
                element.checked = originalState;
            })
            .finally(() => {
                element.disabled = false;
            });
        }

        function resolveAction(btnElement, actionId, decision) {
            const originalText = btnElement.innerHTML;
            const actionRow = document.getElementById('action-row-' + actionId);
            const buttons = actionRow.querySelectorAll('button');
            
            buttons.forEach(btn => btn.disabled = true);
            btnElement.innerHTML = '<span class="spinner"></span> Obrada...';
            
            fetch('/superadmin-ai/api/resolve-action/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    action_id: actionId,
                    decision: decision
                })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                        throw new Error(errData.message || 'Greška servera pri procesiranju akcije.');
                    });
                }
                return response.json();
            })
            .then(res => {
                showToast('success', res.message || 'Akcija je uspješno obrađena.');
                actionRow.style.opacity = '0.3';
                actionRow.style.pointerEvents = 'none';
                btnElement.innerHTML = decision === 'APPROVED' ? 'Odobreno' : 'Odbijeno';
            })
            .catch(error => {
                showToast('error', error.message);
                buttons.forEach(btn => btn.disabled = false);
                btnElement.innerHTML = originalText;
            });
        }
    </script>
</body>
</html>
"""

with open(dashboard_path, "w", encoding="utf-8") as f:
    f.write(html_content)

# 3. Restrukturiranje views.py sa zahtijevanim arhitektonskim izmjenama
print_status("Implementiram sync_local_modules i @require_POST u views.py...")

views_content = textwrap.dedent("""\
    import json
    from django.shortcuts import render
    from django.http import JsonResponse
    from django.apps import apps
    from django.contrib.auth.decorators import user_passes_test
    from django.views.decorators.http import require_POST
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
    from .models import AIModuleAccess, AIActionQueue
    # from . import services  # Otkomentiraj ako C Code koristi specifične servise

    def sync_local_modules():
        \"\"\"Automatski detektira i dodaje sve lokalne Django aplikacije u bazu dozvola.\"\"\"
        for app_config in apps.get_app_configs():
            if not app_config.name.startswith('django.') and not app_config.name.startswith('rest_framework'):
                AIModuleAccess.objects.get_or_create(module_name=app_config.name)

    @user_passes_test(lambda u: u.is_superuser)
    def dashboard(request):
        sync_local_modules()
        modules = AIModuleAccess.objects.all().order_by('module_name')
        actions = AIActionQueue.objects.filter(status='PENDING').order_by('-created_at')
        return render(request, 'superadmin_ai/dashboard.html', {
            'modules': modules,
            'actions': actions
        })

    @require_POST
    @user_passes_test(lambda u: u.is_superuser)
    def update_permission(request):
        try:
            data = json.loads(request.body)
            module_id = data.get('module_id')
            perm_type = data.get('permission_type')
            value = data.get('value')
            
            # TODO: Zamijeni direktni ORM sa svojim services.py ako se koristi audit log
            module = AIModuleAccess.objects.get(id=module_id)
            if perm_type == 'read':
                module.can_read = value
            elif perm_type == 'write':
                module.can_write = value
            elif perm_type == 'create':
                module.can_create = value
            elif perm_type == 'modify':
                module.can_modify = value
            module.save()
            
            return JsonResponse({'status': 'success', 'message': f'Dozvole za {module.module_name} ažurirane.'})
        except AIModuleAccess.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Modul nije pronađen u bazi.'}, status=404)
        except ObjectDoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    @require_POST
    @user_passes_test(lambda u: u.is_superuser)
    def resolve_action(request):
        try:
            data = json.loads(request.body)
            action_id = data.get('action_id')
            decision = data.get('decision')
            
            # TODO: Zamijeni sa services.py metodom za integraciju audit loga
            action = AIActionQueue.objects.get(id=action_id)
            action.status = decision
            action.save()
            
            msg = "odobrena" if decision == 'APPROVED' else "odbijena"
            return JsonResponse({'status': 'success', 'message': f'AI Akcija {msg}.'})
        except AIActionQueue.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Akcija nije pronađena.'}, status=404)
        except ObjectDoesNotExist as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
""")

with open(views_path, "w", encoding="utf-8") as f:
    f.write(views_content)

# 4. Zaključavanje dozvola
print_status("Postavljam Linux dozvole (chown www-data) za modificirane datoteke...")
subprocess.run(["chown", "-R", "www-data:www-data", app_dir])

print_status("UPGRADE ZAVRŠEN! Sustav sada koristi C Code arhitekturu uz Premium UI i potpunu automatizaciju.")
