from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registration", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysubscription",
            name="modules_override",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text="Custom module list; overrides plan if set",
            ),
        ),
    ]
