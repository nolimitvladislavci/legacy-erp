from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("delivery", "0009_transport_module")]
    operations = [
        migrations.AddField(
            model_name="transportorder",
            name="posting_document",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="posting_orders",
                to="delivery.driverdocument",
                verbose_name="Posting Declaration dokument",
            ),
        ),
    ]
