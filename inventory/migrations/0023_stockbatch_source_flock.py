from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0022_source_flock'),
        ('udruge', '0013_flock_modul'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockbatch',
            name='source_flock',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='LOT-level karencija: blokira samo OVU šaržu, ne sve artikle',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_batches',
                to='udruge.flock',
                verbose_name='Izvorno jato',
            ),
        ),
    ]
