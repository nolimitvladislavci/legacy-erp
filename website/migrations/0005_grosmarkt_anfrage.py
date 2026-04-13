from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0004_companywebsite_websitecontactmessage_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="GrosmarktAnfrage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Ime i prezime")),
                ("company", models.CharField(max_length=200, verbose_name="Firma / Unternehmen")),
                ("email", models.EmailField(max_length=254, verbose_name="E-Mail")),
                ("phone", models.CharField(blank=True, max_length=50, verbose_name="Telefon")),
                ("message", models.TextField(blank=True, verbose_name="Poruka / Nachricht")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Nova / Neu"),
                            ("contacted", "Kontaktiran"),
                            ("demo_done", "Demo odrađen"),
                            ("converted", "Konvertiert"),
                            ("declined", "Abgelehnt"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("contacted_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, verbose_name="Interne Notizen")),
            ],
            options={
                "verbose_name": "Grosmarkt Anfrage",
                "verbose_name_plural": "Grosmarkt Anfragen",
                "ordering": ["-created_at"],
            },
        ),
    ]
