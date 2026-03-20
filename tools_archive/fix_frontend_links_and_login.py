import os
import re

print("🚀 INICIJALIZACIJA: Spajanje web stranice i vraćanje Login forme...")

base_dir = '/var/www/fina-connect'

# ==========================================
# 1. VRAĆANJE PREMIUM LOGIN FORME
# ==========================================
login_html = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prijava - LIMIT CONNECT</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #0f172a 0%, #020617 100%);
            height: 100vh;
            display: flex; align-items: center; justify-content: center;
            font-family: 'Segoe UI', system-ui, sans-serif; margin: 0;
        }
        .login-card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px; padding: 40px;
            width: 100%; max-width: 420px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .logo-text {
            color: white; font-weight: 800; font-size: 1.8rem;
            text-align: center; margin-bottom: 30px; letter-spacing: 1px;
        }
        .logo-text span { color: #c9a84c; }
        .form-control {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white; padding: 12px 15px; border-radius: 8px;
        }
        .form-control:focus {
            background: rgba(15, 23, 42, 0.8); border-color: #c9a84c;
            box-shadow: 0 0 0 0.25rem rgba(201, 168, 76, 0.25); color: white;
        }
        .btn-primary {
            background: #c9a84c; border: none; color: #0f172a;
            font-weight: 700; padding: 12px; border-radius: 8px;
            letter-spacing: 0.5px; transition: all 0.3s;
        }
        .btn-primary:hover { background: #e8c96a; transform: translateY(-2px); }
        .form-label { color: #94a3b8; font-size: 0.9rem; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo-text">FINA-<span>CONNECT</span></div>
        {% if form.errors or error %}
        <div class="alert alert-danger border-0 bg-danger text-white" style="background-color: rgba(220,53,69,0.2) !important;">
            Pogrešno korisničko ime ili lozinka.
        </div>
        {% endif %}
        <form method="post" action="{% url 'login' %}">
            {% csrf_token %}
            <div class="mb-4">
                <label class="form-label">Korisničko ime</label>
                <div class="input-group">
                    <span class="input-group-text bg-transparent border-end-0" style="border-color: rgba(255,255,255,0.1); color: #94a3b8;"><i class="fas fa-user"></i></span>
                    <input type="text" name="username" class="form-control border-start-0" required autofocus>
                </div>
            </div>
            <div class="mb-4">
                <label class="form-label">Lozinka</label>
                <div class="input-group">
                    <span class="input-group-text bg-transparent border-end-0" style="border-color: rgba(255,255,255,0.1); color: #94a3b8;"><i class="fas fa-lock"></i></span>
                    <input type="password" name="password" class="form-control border-start-0" required>
                </div>
            </div>
            <button type="submit" class="btn btn-primary w-100 mt-2">Prijava u ERP sustav</button>
        </form>
        <div class="text-center mt-4">
            <a href="/" class="text-decoration-none" style="color: #64748b; font-size: 0.85rem;"><i class="fas fa-arrow-left me-1"></i> Povratak na naslovnicu</a>
        </div>
    </div>
</body>
</html>"""

# Da budemo 100% sigurni da će ju Django povući, spremit ćemo je na dvije standardne lokacije
login_paths = [
    f'{base_dir}/templates/login.html',
    f'{base_dir}/templates/registration/login.html',
    f'{base_dir}/accounts/templates/accounts/login.html'
]

for path in login_paths:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(login_html)
print("✅ Premium Login forma je uspješno obnovljena i zaključana na mjestu.")


# ==========================================
# 2. DODAVANJE LINKOVA NA WEB STRANICU
# ==========================================
website_template = f'{base_dir}/website/templates/website/homepage.html'

if os.path.exists(website_template):
    with open(website_template, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ubacivanje linka u glavni izbornik (Nav)
    if 'class="nav-booking"' not in content:
        content = content.replace(
            '<a href="https://limit-connect.com/login/" class="nav-erp">ERP Portal →</a>',
            '<a href="/appointments/booking/" class="nav-booking" style="color: var(--gold); font-weight:600;"><i class="far fa-calendar-check"></i> Rezervacije</a>\n        <a href="/login/" class="nav-erp">ERP Portal →</a>'
        )
    
    # Ubacivanje gumba u Hero sekciju
    if '>Rezerviraj termin<' not in content:
        content = content.replace(
            '<a href="#brendovi" class="btn-primary">Naši brendovi</a>',
            '<a href="/appointments/booking/" class="btn-primary" style="background: var(--white); color: var(--black);">Rezerviraj termin</a>\n        <a href="#brendovi" class="btn-primary">Naši brendovi</a>'
        )

    with open(website_template, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Zlatni gumbi za Rezervacije su dodani na tvoju Viskovic Group stranicu.")
else:
    print(f"⚠️ Nisam pronašao datoteku na {website_template}. Ako se nalazi drugdje, javi!")

# Popravljamo dozvole i restartamo server
os.system(f"chown -R www-data:www-data {base_dir}")
os.system("supervisorctl restart fina-connect")
print("✨ Sustav osvježen! Promjene su sada vidljive.")
