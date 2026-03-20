from django.db.models.signals import post_save
from django.dispatch import receiver


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
