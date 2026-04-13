from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("experiences", "0001_initial"),
        ("invoicing", "0033_invoiceitem_section_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="experiencebooking",
            name="forfeited_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="forfeited_bookings",
                to="invoicing.invoice",
                verbose_name="Račun za zadržani depozit",
            ),
        ),
    ]
