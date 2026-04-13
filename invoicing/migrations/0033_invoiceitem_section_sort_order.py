from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0032_branch_location_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceitem",
            name="section",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Naziv sekcije npr. "Teil 1 — Arbeitsleistungen". Prazno = bez sekcije.',
                max_length=150,
                verbose_name="Sekcija",
            ),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="sort_order",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Redoslijed unutar sekcije (0, 10, 20...)",
                verbose_name="Redoslijed",
            ),
        ),
    ]
