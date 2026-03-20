from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('inventory', '0002_inventoryitem_barcode_inventoryitem_company_and_more')]
    operations = [
        migrations.AddField(
            model_name='InventoryItem',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='inventory/', verbose_name='Slika'),
        ),
        migrations.AddField(
            model_name='InventoryItem',
            name='webshop_visible',
            field=models.BooleanField(default=False, verbose_name='Vidljiv u webshopu'),
        ),
    ]
