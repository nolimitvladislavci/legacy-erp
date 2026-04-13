from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("experiences", "0002_forfeited_invoice"),
        ("invoicing", "0033_invoiceitem_section_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="experiencebooking",
            name="deposit_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Izdaje se pri potvrdi depozita — čl.79 ZPDV",
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deposit_bookings",
                to="invoicing.invoice",
                verbose_name="Avansni račun (predujam)",
            ),
        ),
        migrations.AlterField(
            model_name="experienceinclusion",
            name="quantity_per_person",
            field=models.DecimalField(
                decimal_places=4,
                default=1,
                max_digits=8,
                help_text="Točna količina po 1 osobi u jedinicama artikla (kg, L, kom...)",
                verbose_name="Normativ po osobi",
            ),
        ),
    ]
