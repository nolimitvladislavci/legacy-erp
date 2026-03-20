import os


def fix():
    template_path = '/var/www/fina-connect/templates/invoicing/invoice_form.html'

    # Koristimo tvoje točne nazive ruta: index i invoice_save
    html_content = """{% extends 'base.html' %}
{% block content %}
<div class="stat-card">
    <h4><i class="fas fa-file-invoice me-2"></i>Novi račun</h4>
    <form method="post" action="{% url 'invoicing:invoice_save' %}">
        {% csrf_token %}
        <div class="row mt-4">
            <div class="col-md-8 mb-3">
                <label class="form-label fw-bold">Ime klijenta</label>
                <input type="text" name="client_name" class="form-control" required 
                       placeholder="Obavezno polje (npr. VODOCOMP d.o.o.)">
            </div>
            <div class="col-md-4 mb-3">
                <label class="form-label fw-bold">Datum izdavanja</label>
                <input type="date" name="date_issued" class="form-control" value="{% now 'Y-m-d' %}">
            </div>
        </div>
        <hr>
        <div class="d-flex gap-2 justify-content-end">
            <a href="{% url 'invoicing:index' %}" class="btn btn-outline-secondary">Odustani</a>
            <button type="submit" class="btn btn-primary">Spremi i dodaj stavke</button>
        </div>
    </form>
</div>
{% endblock %}
"""
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Osiguravanje dozvola [cite: 2026-02-17]
    os.system("chown www-data:www-data " + template_path)
    print("✓ Predložak ispravljen s rutama 'index' i 'invoice_save'.")

if __name__ == "__main__":
    fix()
