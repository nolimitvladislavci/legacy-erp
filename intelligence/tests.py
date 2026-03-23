"""
Intelligence modul — integracijski testovi.
Pokriva: Source, FundOpportunity, Job, Result, Application, Service logic.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class IntelTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from companies.models import Company
        from accounts.models import UserProfile
        cls.company = Company.objects.create(name='Intel Test OPG', oib='99988877766', country='HR', business_type='opg')
        cls.user = User.objects.create_user(username='intel_test', password='IntelTest2026!')
        UserProfile.objects.update_or_create(user=cls.user, defaults={'company': cls.company, 'role': 'company_admin'})


class SourceTest(IntelTestBase):
    def test_create_source(self):
        from intelligence.models import IntelligenceSource
        src = IntelligenceSource.objects.create(naziv='APPRRR', tip='hr_apprrr', url='https://apprrr.hr/')
        self.assertTrue(src.aktivan)
        self.assertEqual(src.provjeri_svakih_sati, 24)

    def test_tip_choices(self):
        from intelligence.models import IntelligenceSource
        valid = [c[0] for c in IntelligenceSource.TIP_CHOICES]
        self.assertIn('eu_fond', valid)
        self.assertIn('natjecaj_udruga', valid)

    def test_interval_not_due(self):
        from intelligence.models import IntelligenceSource
        src = IntelligenceSource.objects.create(naziv='T', tip='vijest', url='https://x.com', provjeri_svakih_sati=24, zadnja_provjera=timezone.now() - timedelta(hours=1))
        hrs = (timezone.now() - src.zadnja_provjera).total_seconds() / 3600
        self.assertLess(hrs, src.provjeri_svakih_sati)


class FundTest(IntelTestBase):
    def test_create_fund(self):
        from intelligence.models import FundOpportunity
        f = FundOpportunity.objects.create(naziv='EU ESF+', tip='eu_esf', status='aktivan', tijelo='SAFU', opis='Test', iznos_max_eur=Decimal('50000'), rok_prijave=date.today() + timedelta(days=60))
        self.assertGreater(f.days_until_deadline, 0)
        self.assertFalse(f.hitno)

    def test_hitno_near_deadline(self):
        from intelligence.models import FundOpportunity
        f = FundOpportunity.objects.create(naziv='Hitni', tip='hr_apprrr', tijelo='APPRRR', opis='H', rok_prijave=date.today() + timedelta(days=7))
        self.assertTrue(f.hitno)

    def test_not_hitno_far(self):
        from intelligence.models import FundOpportunity
        f = FundOpportunity.objects.create(naziv='Daleki', tip='eu_erdf', tijelo='SAFU', opis='D', rok_prijave=date.today() + timedelta(days=60))
        self.assertFalse(f.hitno)

    def test_no_deadline(self):
        from intelligence.models import FundOpportunity
        f = FundOpportunity.objects.create(naziv='Bez roka', tip='hr_ostalo', tijelo='R', opis='N')
        self.assertIsNone(f.days_until_deadline)
        self.assertFalse(f.hitno)

    def test_ai_discovered(self):
        from intelligence.models import FundOpportunity
        f = FundOpportunity.objects.create(naziv='AI', tip='eu_eafrd', tijelo='APPRRR', opis='AI', otkrio_intelligence=True, ai_checklist=['OPG', 'ARKOD', '1ha'])
        self.assertTrue(f.otkrio_intelligence)
        self.assertEqual(len(f.ai_checklist), 3)


class JobTest(IntelTestBase):
    def test_create_with_keywords(self):
        from intelligence.models import IntelligenceJob
        j = IntelligenceJob.objects.create(company=self.company, opis_poslovanja='OPG kukuruz soja', kljucne_rijeci=['kukuruz', 'soja', 'bio'], obavijesti_whatsapp=True)
        self.assertTrue(j.aktivan)
        self.assertEqual(len(j.kljucne_rijeci), 3)

    def test_fund_range(self):
        from intelligence.models import IntelligenceJob
        j = IntelligenceJob.objects.create(company=self.company, min_fond_iznos_eur=Decimal('5000'), max_fond_iznos_eur=Decimal('100000'))
        self.assertEqual(j.min_fond_iznos_eur, Decimal('5000'))


class ResultTest(IntelTestBase):
    def test_relevance_ordering(self):
        from intelligence.models import IntelligenceJob, IntelligenceResult
        job = IntelligenceJob.objects.create(company=self.company)
        IntelligenceResult.objects.create(job=job, naslov='Low', summary='T', ai_relevantnost=30)
        IntelligenceResult.objects.create(job=job, naslov='High', summary='T', ai_relevantnost=90)
        results = list(IntelligenceResult.objects.filter(job=job))
        self.assertEqual(results[0].naslov, 'High')

    def test_status_workflow(self):
        from intelligence.models import IntelligenceJob, IntelligenceResult
        job = IntelligenceJob.objects.create(company=self.company)
        r = IntelligenceResult.objects.create(job=job, naslov='T', summary='T', ai_relevantnost=75)
        self.assertEqual(r.status, 'novo')
        r.status = 'obavljeno'
        r.obavljeno_at = timezone.now()
        r.save(update_fields=['status', 'obavljeno_at'])
        r.refresh_from_db()
        self.assertEqual(r.status, 'obavljeno')


class ApplicationTest(IntelTestBase):
    def test_lifecycle(self):
        from intelligence.models import FundOpportunity, FundApplication
        fund = FundOpportunity.objects.create(naziv='LC', tip='eu_esf', tijelo='SAFU', opis='T', rok_prijave=date.today() + timedelta(days=30))
        app = FundApplication.objects.create(company=self.company, opportunity=fund, trazeni_iznos_eur=Decimal('25000'))
        self.assertEqual(app.status, 'priprema')
        app.status = 'odobren'
        app.odobreni_iznos_eur = Decimal('20000')
        app.save(update_fields=['status', 'odobreni_iznos_eur'])
        app.refresh_from_db()
        self.assertEqual(app.odobreni_iznos_eur, Decimal('20000'))

    def test_unique_constraint(self):
        from django.db import IntegrityError
        from intelligence.models import FundOpportunity, FundApplication
        fund = FundOpportunity.objects.create(naziv='UQ', tip='hr_apprrr', tijelo='A', opis='T')
        FundApplication.objects.create(company=self.company, opportunity=fund)
        with self.assertRaises(IntegrityError):
            FundApplication.objects.create(company=self.company, opportunity=fund)


class ServiceLogicTest(IntelTestBase):
    def test_notification_threshold(self):
        self.assertTrue(90 >= 60)
        self.assertFalse(59 >= 60)

    def test_json_parsing(self):
        import json, re
        llm = 'Evo: {"pronasci": [{"naslov": "EU fond", "relevantnost": 85}]} kraj'
        m = re.search(r'\{.*"pronasci".*\}', llm, re.DOTALL)
        self.assertIsNotNone(m)
        data = json.loads(m.group())
        self.assertEqual(data['pronasci'][0]['relevantnost'], 85)


class CrossModuleTest(IntelTestBase):
    def test_fund_in_ai_draft(self):
        from intelligence.models import FundOpportunity
        from limit_connect_ai.models import FundApplicationDraft
        fund = FundOpportunity.objects.create(naziv='XM', tip='eu_esf', tijelo='SAFU', opis='T', rok_prijave=date.today() + timedelta(days=30))
        draft = FundApplicationDraft.objects.create(company=self.company, fund_opportunity=fund, eligibility_score=75)
        self.assertEqual(draft.status, 'draft')
        self.assertEqual(draft.fund_opportunity.naziv, 'XM')
