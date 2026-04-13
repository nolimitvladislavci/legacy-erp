import os


def sync():
    urls_path = '/var/www/fina-connect/invoicing/urls.py'
    template_dir = '/var/www/fina-connect/templates/invoicing'

    # 1. Usklađivanje URL-ova (Dodavanje 'new/' ako nedostaje) [cite: 2026-02-17]
    with open(urls_path, 'r', encoding='utf-8') as f:
        urls_content = f.read()

    if "path('new/'," not in urls_content:
        # Ubacujemo 'new/' odmah iznad 'create/'
        new_line = "    path('new/', views.invoice_create, name='invoice_create'),\n"
        urls_content = urls_content.replace("path('create/',", new_line + "    path('create/',")
        with open(urls_path, 'w', encoding='utf-8') as f:
            f.write(urls_content)
        print("✓ Ruta 'new/' dodana u urls.py.")

    # 2. Masovna sinkronizacija predložaka [cite: 2026-02-17]
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    # Koristimo tvoj potvrđeni client_name i rute 'index' te 'invoice_save' [cite: 2026-01-25]
    html_body = """{% extends 'base.html' %}
{% block content %}
<div class="stat-card">
    <h4><i class="fas fa-plus-circle me-2"></i>Novi račun</h4>
    <form method="post" action="{% url 'invoicing:invoice_save' %}">
        {% csrf_token %}
        <div class="row mt-4">
            <div class="col-md-8 mb-3">
                <label class="form-label fw-bold">Naziv klijenta</label>
                <input type="text" name="client_name" class="form-control" required placeholder="VODOCOMP d.o.o.">
            </div>
            <div class="col-md-4 mb-3">
                <label class="form-label fw-bold">Datum</label>
                <input type="date" name="date_issued" class="form-control" value="{% now 'Y-m-d' %}">
            </div>
        </div>
        <div class="mt-3">
            <button type="submit" class="btn btn-primary">Spremi i nastavi</button>
            <a href="{% url 'invoicing:index' %}" class="btn btn-outline-secondary">Odustani</a>
        </div>
    </form>
</div>
{% endblock %}
"""
    # Pišemo u oba moguća naziva kako bismo izbjegli TemplateDoesNotExist [cite: 2026-02-17]
    for name in ['invoice_form.html', 'invoice_create.html']:
        with open(os.path.join(template_dir, name), 'w', encoding='utf-8') as f:
            f.write(html_body)

    os.system(f"chown -R www-data:www-data {template_dir}")
    print("✓ Predlošci sinkronizirani (form i create).")

if __name__ == "__main__":
    sync()
