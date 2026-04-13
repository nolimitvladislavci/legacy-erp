import uuid
from django.db import migrations, models


def gen_tokens(apps, schema_editor):
    Invoice = apps.get_model("invoicing", "Invoice")
    for inv in Invoice.objects.filter(client_token=None):
        inv.client_token = uuid.uuid4()
        inv.save(update_fields=["client_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0009_workflow_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="client_token",
            field=models.UUIDField(blank=True, null=True, verbose_name="Client portal token"),
        ),
        migrations.RunPython(gen_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="invoice",
            name="client_token",
            field=models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="Client portal token"),
        ),
    ]
