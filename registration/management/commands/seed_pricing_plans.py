from django.core.management.base import BaseCommand
from registration.models import PricingPlan


PLANS = [
    {
        'slug': 'starter',
        'name': 'Starter',
        'name_de': 'Starter',
        'name_en': 'Starter',
        'tagline': 'Za male tvrtke i obrte',
        'tagline_de': 'Fuer kleine Unternehmen',
        'price_monthly': 9,
        'price_yearly': 89,
        'max_users': 3,
        'max_locations': 1,
        'max_invoices_per_month': 50,
        'max_articles': 100,
        'storage_mb': 500,
        'included_modules': ['invoicing', 'partners', 'documents', 'calculator'],
        'has_fiscalization': True,
        'sort_order': 1,
    },
    {
        'slug': 'professional',
        'name': 'Professional',
        'name_de': 'Professional',
        'name_en': 'Professional',
        'tagline': 'Za rastuce tvrtke',
        'tagline_de': 'Fuer wachsende Unternehmen',
        'price_monthly': 29,
        'price_yearly': 290,
        'max_users': 15,
        'max_locations': 3,
        'max_invoices_per_month': 500,
        'max_articles': 1000,
        'storage_mb': 5000,
        'included_modules': [
            'invoicing', 'partners', 'documents', 'calculator',
            'worktime', 'projects', 'konto', 'appointments',
            'booking', 'burza', 'tracking', 'gastro', 'reports',
        ],
        'has_fiscalization': True,
        'has_whatsapp': True,
        'is_popular': True,
        'sort_order': 2,
    },
    {
        'slug': 'enterprise',
        'name': 'Enterprise',
        'name_de': 'Enterprise',
        'name_en': 'Enterprise',
        'tagline': 'Kompletno ERP rjesenje',
        'tagline_de': 'Komplette ERP-Loesung',
        'price_monthly': 79,
        'price_yearly': 790,
        'max_users': 999,
        'max_locations': 99,
        'max_invoices_per_month': 99999,
        'max_articles': 99999,
        'storage_mb': 50000,
        'included_modules': [
            'invoicing', 'partners', 'documents', 'calculator',
            'worktime', 'projects', 'konto', 'appointments',
            'booking', 'burza', 'tracking', 'gastro', 'reports',
            'finance', 'inventory', 'insurance', 'webshop', 'rental',
            'fitness', 'interventions', 'assessment', 'outreach',
            'ai_assistant', 'pos',
        ],
        'has_fiscalization': True,
        'has_whatsapp': True,
        'has_api_access': True,
        'has_premium_support': True,
        'has_custom_branding': True,
        'sort_order': 3,
    },
]


class Command(BaseCommand):
    help = 'Seed PricingPlan data (Starter / Professional / Enterprise)'

    def handle(self, *args, **options):
        for plan_data in PLANS:
            obj, created = PricingPlan.objects.update_or_create(
                slug=plan_data['slug'],
                defaults=plan_data,
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'{status}: {obj}')
        self.stdout.write(self.style.SUCCESS('Pricing plans seeded successfully.'))
