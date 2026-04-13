"""Seed GovExport institucije i tipove dokumenata."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed GovExport institucije i tipove dokumenata'

    def handle(self, *args, **options):
        from gov_export.models import GovDocumentType, GovInstitution

        institutions = [
            {'code': 'PU', 'name': 'Porezna uprava', 'transport': 'soap', 'auth_type': 'cert',
             'endpoint_url': 'https://e-porezna.porezna-uprava.hr/', 'requires_signature': True},
            {'code': 'FINA', 'name': 'FINA', 'transport': 'rest', 'auth_type': 'cert',
             'endpoint_url': 'https://eracun.fina.hr/', 'requires_signature': True},
            {'code': 'HZZO', 'name': 'HZZO', 'transport': 'upload', 'auth_type': 'none',
             'requires_signature': False},
            {'code': 'DZS', 'name': 'Državni zavod za statistiku', 'transport': 'upload', 'auth_type': 'none',
             'requires_signature': False},
            {'code': 'SANIT', 'name': 'Sanitarna inspekcija', 'transport': 'upload', 'auth_type': 'none',
             'requires_signature': False},
        ]

        for data in institutions:
            inst, created = GovInstitution.objects.update_or_create(
                code=data['code'], defaults=data,
            )
            self.stdout.write(f'  {"+" if created else "~"} {inst}')

        doc_types = [
            {'institution_code': 'PU', 'code': 'JOPPD', 'name': 'JOPPD — Izvješće o primicima i doprinosima',
             'period_type': 'monthly', 'deadline_rule': '15. u mjesecu za prethodni',
             'xml_namespace': 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/ObscePorezanDohodak/v4-0',
             'generator_class': 'gov_export.generators.joppd.JOPPDGenerator'},
            {'institution_code': 'PU', 'code': 'PDV-S', 'name': 'PDV-S — Prijava PDV-a',
             'period_type': 'monthly', 'deadline_rule': '20. u mjesecu za prethodni'},
            {'institution_code': 'PU', 'code': 'DOH', 'name': 'DOH — Prijava poreza na dohodak',
             'period_type': 'yearly', 'deadline_rule': '28. veljače za prethodnu godinu'},
            {'institution_code': 'PU', 'code': 'SAF-T', 'name': 'SAF-T HR — Standard Audit File for Tax',
             'period_type': 'on_demand', 'deadline_rule': 'Na zahtjev Porezne'},
            {'institution_code': 'PU', 'code': 'eRACUN', 'name': 'eRačun — Fiskalizacija 2.0',
             'period_type': 'realtime'},
            {'institution_code': 'FINA', 'code': 'PR-RAS-NPF', 'name': 'PR-RAS-NPF — Financijski izvještaj (udruge)',
             'period_type': 'yearly', 'deadline_rule': '1. ožujka za prethodnu godinu'},
            {'institution_code': 'FINA', 'code': 'BIL-NPF', 'name': 'BIL-NPF — Bilanca (udruge)',
             'period_type': 'yearly'},
            {'institution_code': 'SANIT', 'code': 'HACCP', 'name': 'HACCP Recall Report',
             'period_type': 'on_demand'},
        ]

        for data in doc_types:
            inst_code = data.pop('institution_code')
            inst = GovInstitution.objects.get(code=inst_code)
            dt, created = GovDocumentType.objects.update_or_create(
                institution=inst, code=data['code'], defaults=data,
            )
            self.stdout.write(f'  {"+" if created else "~"} {dt}')


        # ── Novi standardi (LIMIT Connect inovacija) ──
        new_types = [
            {'institution_code': 'SANIT', 'code': 'AGRO-HEALTH', 'name': 'Agro-Fiskalizacija — AgroHealth Report',
             'period_type': 'monthly', 'generator_class': 'gov_export.generators.agro_health.AgroHealthGenerator'},
            {'institution_code': 'PU', 'code': 'TOURIST-ZKI', 'name': 'Turistički ZKI — Asinkrona prijava gostiju',
             'period_type': 'monthly', 'generator_class': 'gov_export.generators.tourist_registration.TouristRegistrationGenerator'},
            {'institution_code': 'PU', 'code': 'INV-LEDGER', 'name': 'Forenzika Zaliha — InventoryLedger',
             'period_type': 'monthly', 'generator_class': 'gov_export.generators.inventory_ledger.InventoryLedgerGenerator'},
        ]
        for data in new_types:
            inst_code = data.pop('institution_code')
            inst = GovInstitution.objects.get(code=inst_code)
            dt, created = GovDocumentType.objects.update_or_create(
                institution=inst, code=data['code'], defaults=data,
            )
            self.stdout.write(f'  {"+" if created else "~"} {dt}')

        self.stdout.write(self.style.SUCCESS('Done.'))
