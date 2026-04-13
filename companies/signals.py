import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import IntegrityError, DatabaseError


@receiver(post_save, sender='partners.Partner')
def on_partner_saved(sender, instance, created, **kwargs):
    if not created:
        return
    company = instance.company
    if not company:
        return
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.first_partner_added:
        ob.first_partner_added = True
        ob.save(update_fields=['first_partner_added', 'updated_at'])


@receiver(post_save, sender='invoicing.Invoice')
def on_invoice_saved(sender, instance, created, **kwargs):
    if not created:
        return
    company = instance.company
    if not company:
        return
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.first_invoice_created:
        ob.first_invoice_created = True
        ob.save(update_fields=['first_invoice_created', 'updated_at'])


@receiver(post_save, sender='konto.BankAccount')
def on_bank_account_saved(sender, instance, created, **kwargs):
    if not created:
        return
    # BankAccount links to company via konto relationships — best-effort
    try:
        company = instance.company
    except AttributeError:
        return
    if not company:
        return
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.bank_account_added:
        ob.bank_account_added = True
        ob.save(update_fields=['bank_account_added', 'updated_at'])


@receiver(post_save, sender='companies.Company')
def auto_create_invoice_profile(sender, instance, created, **kwargs):
    """Auto-create InvoiceProfile when a new Company is created."""
    if not created:
        return
    from invoicing.fiscal_models import InvoiceProfile
    # Don't create if one already exists
    if InvoiceProfile.objects.filter(company=instance).exists():
        return
    country = getattr(instance, 'country', 'HR') or 'HR'
    InvoiceProfile.objects.create(
        company=instance,
        name=instance.name,
        company_name=instance.name,
        address=instance.address or '',
        city=instance.city or '',
        zip_code=instance.zip_code or '',
        country=country,
        oib=instance.oib or '',
        iban=instance.iban or '',
        swift=instance.swift or '',
        invoice_prefix=instance.name[:3].upper(),
        is_default=True,
        is_active=True,
    )


@receiver(post_save, sender='companies.Company')
def bootstrap_new_company(sender, instance, created, **kwargs):
    """
    Auto-bootstrap nova firma — kreira sve potrebne objekte za rad.
    Zlatni kod: firma mora biti operativna odmah nakon kreiranja.
    """
    if not created:
        return

    import logging
    logger = logging.getLogger('companies.bootstrap')

    # 1. POS Settings
    try:
        from pos.models import POSSettings
        POSSettings.objects.get_or_create(
            company=instance,
            defaults={
                'printer_type': 'thermal_usb',
                'receipt_delivery': 'thermal',
                'fiscal_oib': instance.oib or '',
            },
        )
    except DatabaseError as e:
        logger.warning('[BOOTSTRAP] POSSettings za %s: %s', instance.name, e)

    # 2. Default POS Terminal
    try:
        from pos.models import POSTerminal
        if not POSTerminal.objects.filter(company=instance).exists():
            POSTerminal.objects.create(
                company=instance,
                name='Blagajna 1',
                terminal_code='T001',
                pos_type='quick',
                is_active=True,
            )
    except (IntegrityError, DatabaseError) as e:
        logger.warning('[BOOTSTRAP] POSTerminal za %s: %s', instance.name, e)

    # 3. Default Tax Rates (HR)
    try:
        from companies.models import TaxRate
        country = getattr(instance, 'country', 'HR') or 'HR'
        defaults = {
            'HR': [
                ('PDV 25%', 25, True),
                ('PDV 13%', 13, False),
                ('PDV 5%', 5, False),
                ('Oslobođeno', 0, False),
            ],
            'DE': [
                ('MwSt 19%', 19, True),
                ('MwSt 7%', 7, False),
                ('PDV 0% (Oslobođeno)', 0, False),
            ],
        }
        for name, rate, is_default in defaults.get(country, defaults['HR']):
            TaxRate.objects.get_or_create(
                country=country, rate=rate,
                defaults={'name': name, 'is_default': is_default, 'is_active': True},
            )
    except DatabaseError as e:
        logger.warning('[BOOTSTRAP] TaxRate za %s: %s', instance.name, e)

    # 4. Onboarding Progress
    try:
        from companies.models import OnboardingProgress
        OnboardingProgress.objects.get_or_create(company=instance)
    except DatabaseError as e:
        logger.warning('[BOOTSTRAP] OnboardingProgress za %s: %s', instance.name, e)

    # 5. T&C default (unsigned)
    try:
        if not hasattr(instance, 'has_signed_tc_consent'):
            pass  # Field will be False by default
    except Exception:
        pass

    logger.info('[BOOTSTRAP] Firma "%s" (OIB %s) bootstrapirana.', instance.name, instance.oib)

import companies.data_quality  # noqa: F401 — Data Quality Guard


@receiver(post_save, sender='worktime.EmployeeProfile')
def on_employee_saved(sender, instance, created, **kwargs):
    if not created:
        return
    company = getattr(instance, 'company', None)
    if not company:
        return
    from companies.models import OnboardingProgress
    ob, _ = OnboardingProgress.objects.get_or_create(company=company)
    if not ob.first_employee_added:
        ob.first_employee_added = True
        ob.save(update_fields=['first_employee_added', 'updated_at'])
