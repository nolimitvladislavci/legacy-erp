from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('webshop', '0003_product_available_qty_product_company_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS idx_product_domain_attrs_gin ON webshop_product USING GIN (domain_attrs);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_domain_attrs_gin;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS idx_cartitem_attrs_gin ON webshop_cartitem USING GIN (item_attributes);",
            reverse_sql="DROP INDEX IF EXISTS idx_cartitem_attrs_gin;",
        ),
    ]
