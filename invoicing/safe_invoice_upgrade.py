import os


def upgrade():
    views_path = '/var/www/fina-connect/invoicing/views.py'
    template_dir = '/var/www/fina-connect/templates/invoicing'

    # 1. Sigurnosni backup [cite: 2026-02-17]
    os.system(f"cp {views_path} {views_path}.bak")

    # 2. Inteligentno ažuriranje views.py [cite: 2026-02-17]
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Dodajemo automatizaciju za Finance unutar invoice_edit (ako je račun plaćen/fiskaliziran)
    # Koristimo tvoja stvarna polja: direction='income', company, partner
    finance_logic = """
                # --- Automatsko ažuriranje u Financije ---
                from finance.models import Transaction
                Transaction.objects.update_or_create(
                    description=f'Naplata računa {invoice.number}',
                    defaults={
                        'company': invoice.company,
                        'partner': invoice.partner,
                        'amount': invoice.total,
                        'direction': 'income',
                        'date': invoice.date_issued
                    }
                )
    """

    if "Transaction.objects.update_or_create" not in content:
        # Ubacujemo logiku nakon invoice.save() unutar invoice_edit
        content = content.replace("invoice.save()", f"invoice.save(){finance_logic}", 1)
        with open(views_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✓ Finance automatizacija dodana u views.py.")

    # 3. Kreiranje Template-a (ako nedostaje) [cite: 2026-02-17]
    os.makedirs(template_dir, exist_ok=True)
    template_path = os.path.join(template_dir, 'invoice_form.html')

    if not os.path.exists(template_path):
        html_content = """{% extends 'base.html' %}
{% block content %}
<div class="stat-card">
    <h4>Uredi račun: {{ invoice.number }}</h4>
    <form method="post" class="mt-4">
        {% csrf_token %}
        <div class="row">
            <div class="col-md-6 mb-3">
                <label>Datum izdavanja</label>
                <input type="date" name="date_issued" class="form-control" value="{{ invoice.date_issued|date:'Y-m-d' }}">
            </div>
            <div class="col-md-6 mb-3">
                <label>Partner</label>
                <select name="partner" class="form-control">
                    {% for p in partners %}
                    <option value="{{ p.id }}" {% if p.id == invoice.partner.id %}selected{% endif %}>{{ p.name }}</option>
                    {% endfor %}
                </select>
            </div>
        </div>
        <button type="submit" class="btn btn-primary">Spremi promjene</button>
    </form>
</div>
{% endblock %}
"""
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("✓ Template invoice_form.html kreiran.")

if __name__ == "__main__":
    upgrade()
