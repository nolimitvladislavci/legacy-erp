from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('webshop', '0001_initial'),
        ('inventory', '0003_inventoryitem_image_webshop'),
    ]
    operations = [
        migrations.AddField(
            model_name='product',
            name='inventory_item',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='webshop_product',
                to='inventory.inventoryitem',
                verbose_name='Artikl iz zalihe',
            ),
        ),
    ]
