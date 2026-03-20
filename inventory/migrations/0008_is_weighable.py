from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_kalo'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='is_weighable',
            field=models.BooleanField(
                default=False,
                verbose_name='Prodaje se na vagu',
                help_text='Ako je označeno, POS traži unos težine (kg) pri svakom dodavanju',
            ),
        ),
    ]
