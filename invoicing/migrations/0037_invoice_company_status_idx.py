from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Compound index on (company_id, status) for Invoice.
    Speeds up the frequent filter: Invoice.objects.filter(company=X, status__in=[...])
    Used in: invoice list, overdue update, totals aggregation.
    """

    dependencies = [
        ("invoicing", "0036_add_quote_customer_room_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["company", "status"],
                name="idx_invoice_company_status",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["company", "status", "date_due"],
                name="idx_invoice_company_status_due",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["company", "doctype"],
                name="idx_invoice_company_doctype",
            ),
        ),
    ]
