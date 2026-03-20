from django.db import migrations


def seed_profiles(apps, schema_editor):
    InvoiceProfile = apps.get_model('invoicing', 'InvoiceProfile')
    FiscalConfig = apps.get_model('invoicing', 'FiscalConfig')

    # Skip if profiles already exist
    if InvoiceProfile.objects.exists():
        return

    # Read existing FiscalConfig singleton data
    try:
        config = FiscalConfig.objects.get(pk=1)
    except FiscalConfig.DoesNotExist:
        config = None

    # Create KONJIK HR profile from existing FiscalConfig
    InvoiceProfile.objects.create(
        name='KONJIK HR',
        is_default=True,
        is_active=True,
        company_name=config.company_name if config else 'KONJIK d.o.o.',
        address=config.address if config else '',
        city=config.city if config else 'Zagreb',
        country='HR',
        oib=config.oib if config else '',
        language='hr',
        currency='EUR',
        iban=config.default_iban if config else '',
        invoice_prefix=config.invoice_prefix_hr if config else 'KNJ',
        next_invoice_number=config.next_invoice_number if config else 1,
        cert_path=config.cert_path if config else '',
        cert_password=config.cert_password if config else '',
        use_production=config.use_production if config else False,
        email=config.email_from if config else '',
        default_due_days=15,
        default_payment_method='TRANSAKCIJSKI',
    )

    # Create KONJIK DE stub profile
    InvoiceProfile.objects.create(
        name='KONJIK DE',
        is_default=False,
        is_active=True,
        company_name=config.company_name if config else 'KONJIK d.o.o.',
        address='',
        city='',
        country='DE',
        language='de',
        currency='EUR',
        invoice_prefix='DE',
        next_invoice_number=1,
        default_due_days=30,
        default_payment_method='ÜBERWEISUNG',
    )


def reverse_seed(apps, schema_editor):
    InvoiceProfile = apps.get_model('invoicing', 'InvoiceProfile')
    InvoiceProfile.objects.filter(name__in=['KONJIK HR', 'KONJIK DE']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0011_invoiceprofile_invoice_invoice_profile'),
    ]

    operations = [
        migrations.RunPython(seed_profiles, reverse_seed),
    ]
