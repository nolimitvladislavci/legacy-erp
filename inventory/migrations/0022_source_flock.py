from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0021_split_allocation'),
        ('udruge', '0013_flock_modul'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='source_flock',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='Za karencija enforcement — blokira POS prodaju dok je jato pod lijekovima',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='inventory_products',
                to='udruge.flock',
                verbose_name='Izvorno jato',
            ),
        ),
    ]
