from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
        ("udruge", "0005_dogadjaj_emailkampanja_emaillog_kampanja_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="VolunteerActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("admin", "Administrativno"),
                            ("field", "Terenski rad"),
                            ("event", "Organizacija eventi"),
                            ("education", "Edukacija / Mentoring"),
                            ("fundraising", "Fundraising"),
                            ("it", "IT / Digitalizacija"),
                            ("legal", "Pravna pomoc"),
                            ("social", "Socijalni rad"),
                            ("sports", "Sport / Rekreacija"),
                            ("culture", "Kultura / Umjetnost"),
                            ("environment", "Zastita okolisa"),
                            ("other", "Ostalo"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("date", models.DateField()),
                ("hours", models.DecimalField(decimal_places=2, max_digits=5)),
                ("location", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("planned", "Planirana"),
                            ("in_progress", "U tijeku"),
                            ("completed", "Zavrsena"),
                            ("cancelled", "Otkazana"),
                        ],
                        default="planned",
                        max_length=20,
                    ),
                ),
                ("eu_project_code", models.CharField(blank=True, max_length=100)),
                ("inkind_rate_eur", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "clan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="volunteer_activities",
                        to="udruge.clan",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="volunteer_activities",
                        to="companies.company",
                    ),
                ),
                (
                    "dogadjaj",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="volunteer_activities",
                        to="udruge.dogadjaj",
                    ),
                ),
                (
                    "kampanja",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="volunteer_activities",
                        to="udruge.kampanja",
                    ),
                ),
                (
                    "verified_by",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "db_table": "udruge_volunteer_activity",
                "ordering": ["-date"],
                "indexes": [
                    models.Index(fields=["company", "date"], name="udruge_vol_comp_date_idx"),
                    models.Index(fields=["company", "clan", "date"], name="udruge_vol_comp_clan_idx"),
                ],
            },
        ),
    ]
