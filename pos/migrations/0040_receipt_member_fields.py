"""Add member_name, member_clan_id, member_discount_applied to POSReceipt."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pos", "0039_global_receipt_number")]
    operations = [
        migrations.AddField(
            model_name="posreceipt",
            name="member_name",
            field=models.CharField(blank=True, default="", max_length=200, verbose_name="Ime clana"),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="member_clan_id",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Clan ID"),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="member_discount_applied",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name="Clanski popust (%)"),
        ),
    ]
