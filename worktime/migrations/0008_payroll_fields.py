from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('worktime', '0007_add_legal_fields'),
    ]
    operations = [
        migrations.AddField(
            model_name='timeentry',
            name='regular_hours',
            field=models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                     verbose_name='Redovni sati / Reguläre Stunden'),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='overtime_hours',
            field=models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                     verbose_name='Prekovremeni / Überstunden'),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='night_hours',
            field=models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'),
                                     verbose_name='Noćni sati / Nachtstunden'),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='compliance_note',
            field=models.CharField(max_length=255, blank=True, default='',
                                   verbose_name='Zakonsko upozorenje / Compliance'),
        ),
    ]
