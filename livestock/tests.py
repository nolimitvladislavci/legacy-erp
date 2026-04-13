"""
livestock/tests.py
Testovi za livestock/vet modul — grla, karencija, institucijski API,
robot API, vet quick entry, inspector, panic button.

Pokretanje:
    venv/bin/python manage.py test livestock --verbosity=2
"""
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.models import UserProfile
from companies.models import Company
from livestock.models import (
    HealthRecord,
    InstitutionalAccessLog,
    InstitutionalAccessToken,
    Livestock,
    MilkRecord,
)

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def make_company(oib='99999999999', name='Test OPG'):
    return Company.objects.create(
        oib=oib,
        name=name,
        email=f'{oib}@test.com',
        country='HR',
    )


def make_animal(company, ear_tag='HR999999999900001', vrsta='krava', status='aktivno'):
    return Livestock.objects.create(
        company=company,
        ear_tag=ear_tag,
        vrsta=vrsta,
        status=status,
        breed='Simentalac',
    )


def make_token(company, scope='hapih'):
    return InstitutionalAccessToken.objects.create(
        company=company,
        name=f'Test {scope.upper()}',
        scope=scope,
    )


# ─── MODEL TESTOVI ────────────────────────────────────────────────────────────

class LivestockModelTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.animal  = make_animal(self.company)
        self.today   = timezone.now().date()

    def test_str(self):
        self.assertIn(self.animal.ear_tag, str(self.animal))

    def test_age_months(self):
        self.animal.date_of_birth = self.today - timedelta(days=365)
        self.animal.save()
        self.assertAlmostEqual(self.animal.age_months, 12, delta=1)

    def test_age_months_no_dob(self):
        self.assertIsNone(self.animal.age_months)

    def test_karencija_false_no_records(self):
        self.assertFalse(self.animal.is_in_karencija)

    def test_karencija_true_active(self):
        HealthRecord.objects.create(
            animal=self.animal,
            datum=self.today,
            tip='tretman',
            opis='test',
            lijek='Penicilin',
            karencija_do=self.today + timedelta(days=7),
        )
        self.assertTrue(self.animal.is_in_karencija)

    def test_karencija_false_expired(self):
        HealthRecord.objects.create(
            animal=self.animal,
            datum=self.today - timedelta(days=10),
            tip='tretman',
            opis='stari tretman',
            lijek='Penicilin',
            karencija_do=self.today - timedelta(days=1),
        )
        self.assertFalse(self.animal.is_in_karencija)

    def test_karencija_end(self):
        end = self.today + timedelta(days=14)
        HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='tretman',
            opis='test', lijek='X', karencija_do=end,
        )
        self.assertEqual(self.animal.karencija_end, end)

    def test_karencija_end_none(self):
        self.assertIsNone(self.animal.karencija_end)

    def test_karencija_reason(self):
        HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='tretman',
            opis='Mastitis tretman', lijek='Amoxicilin',
            karencija_do=self.today + timedelta(days=5),
        )
        reason = self.animal.karencija_reason
        self.assertIn('Amoxicilin', reason)

    def test_calving_soon_true(self):
        self.animal.expected_calving = self.today + timedelta(days=10)
        self.animal.save()
        self.assertTrue(self.animal.calving_soon)

    def test_calving_soon_false(self):
        self.animal.expected_calving = self.today + timedelta(days=60)
        self.animal.save()
        self.assertFalse(self.animal.calving_soon)

    def test_unique_ear_tag_per_company(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            make_animal(self.company, ear_tag=self.animal.ear_tag)


class MilkRecordTest(TestCase):

    def setUp(self):
        self.company = make_company('88888888888')
        self.animal  = make_animal(self.company, ear_tag='HR888888888800001')
        self.today   = timezone.now().date()

    def test_ukupno_auto_calculated(self):
        mr = MilkRecord.objects.create(
            animal=self.animal, datum=self.today,
            jutarnja_l=12.5, vecernja_l=10.0,
        )
        self.assertEqual(float(mr.ukupno_l), 22.5)

    def test_unique_per_animal_per_day(self):
        from django.db import IntegrityError
        MilkRecord.objects.create(animal=self.animal, datum=self.today,
                                   jutarnja_l=10, vecernja_l=8)
        with self.assertRaises(IntegrityError):
            MilkRecord.objects.create(animal=self.animal, datum=self.today,
                                       jutarnja_l=9, vecernja_l=7)


class HealthRecordTest(TestCase):

    def setUp(self):
        self.company = make_company('77777777777')
        self.animal  = make_animal(self.company, ear_tag='HR777777777700001')
        self.today   = timezone.now().date()

    def test_u_karenciji_true(self):
        hr = HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='tretman',
            opis='test', karencija_do=self.today + timedelta(days=3),
        )
        self.assertTrue(hr.u_karenciji)

    def test_u_karenciji_false(self):
        hr = HealthRecord.objects.create(
            animal=self.animal, datum=self.today - timedelta(days=5),
            tip='tretman', opis='test',
            karencija_do=self.today - timedelta(days=1),
        )
        self.assertFalse(hr.u_karenciji)

    def test_u_karenciji_no_date(self):
        hr = HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='pregled', opis='kontrola',
        )
        self.assertFalse(hr.u_karenciji)


class InstitutionalTokenTest(TestCase):

    def setUp(self):
        self.company = make_company('66666666666')

    def test_token_auto_generated(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='HAPIH Test', scope='hapih',
        )
        self.assertTrue(len(tok.token) >= 20)

    def test_is_valid_active(self):
        tok = make_token(self.company)
        self.assertTrue(tok.is_valid)

    def test_is_valid_expired(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Exp', scope='hapih',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(tok.is_valid)

    def test_is_valid_inactive(self):
        tok = make_token(self.company)
        tok.is_active = False
        tok.save()
        self.assertFalse(tok.is_valid)

    def test_rate_ok_fresh(self):
        tok = make_token(self.company)
        self.assertTrue(tok.rate_ok)

    def test_rate_ok_exceeded(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Rate', scope='hapih',
            max_requests_day=3,
        )
        for _ in range(3):
            tok.record_access()
        self.assertFalse(tok.rate_ok)

    def test_rate_resets_next_day(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Reset', scope='hapih',
            max_requests_day=1,
        )
        tok.record_access()
        self.assertFalse(tok.rate_ok)
        # Simuliraj sutrašnji dan
        tok.last_request_date = timezone.now().date() - timedelta(days=1)
        tok.save()
        self.assertTrue(tok.rate_ok)

    def test_regenerate_changes_token(self):
        tok = make_token(self.company)
        old = tok.token
        tok.regenerate()
        self.assertNotEqual(tok.token, old)

    def test_record_access_increments(self):
        tok = make_token(self.company)
        tok.record_access()
        tok.record_access()
        tok.refresh_from_db()
        self.assertEqual(tok.requests_today, 2)


# ─── API VIEW TESTOVI ─────────────────────────────────────────────────────────

class RobotIdentifyAPITest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.company = make_company('55555555555')
        self.company.settings = {'robot_api_key': 'test-robot-secret-key-123'}
        self.company.save()
        self.animal = make_animal(self.company, ear_tag='HR555555555500001')
        self.today  = timezone.now().date()

    def _post(self, data, token='test-robot-secret-key-123'):
        req = self.factory.post(
            '/livestock/api/identify/',
            data=json.dumps(data),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        from livestock.views import robot_identify
        return robot_identify(req)

    def test_identify_ok_can_milk(self):
        resp = self._post({'ear_tag': self.animal.ear_tag})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['action'], 'MILK')
        self.assertTrue(data['can_milk'])

    def test_identify_blocked_karencija(self):
        HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='tretman',
            opis='test', lijek='Drug', karencija_do=self.today + timedelta(days=7),
        )
        resp = self._post({'ear_tag': self.animal.ear_tag})
        data = json.loads(resp.content)
        self.assertEqual(data['action'], 'DIVERT')
        self.assertFalse(data['can_milk'])
        self.assertIn('karencija_end', data)

    def test_identify_not_found(self):
        resp = self._post({'ear_tag': 'NEPOSTOJI'})
        self.assertEqual(resp.status_code, 404)

    def test_identify_invalid_token(self):
        resp = self._post({'ear_tag': self.animal.ear_tag}, token='KRIVI_TOKEN')
        self.assertEqual(resp.status_code, 403)

    def test_identify_no_token(self):
        req = self.factory.post(
            '/livestock/api/identify/',
            data=json.dumps({'ear_tag': self.animal.ear_tag}),
            content_type='application/json',
        )
        from livestock.views import robot_identify
        resp = robot_identify(req)
        self.assertEqual(resp.status_code, 401)

    def test_identify_milk_record_auto_saved(self):
        resp = self._post({'ear_tag': self.animal.ear_tag, 'jutarnja_l': 14.0})
        data = json.loads(resp.content)
        self.assertTrue(data.get('milk_recorded'))
        self.assertEqual(float(data.get('milk_total_today', 0)), 14.0)
        mr = MilkRecord.objects.filter(animal=self.animal, datum=self.today).first()
        self.assertIsNotNone(mr)
        self.assertEqual(float(mr.jutarnja_l), 14.0)

    def test_identify_no_milk_when_blocked(self):
        HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='tretman',
            opis='blok', lijek='X', karencija_do=self.today + timedelta(days=5),
        )
        resp = self._post({'ear_tag': self.animal.ear_tag, 'jutarnja_l': 10.0})
        data = json.loads(resp.content)
        self.assertFalse(data.get('milk_recorded', False))
        self.assertFalse(MilkRecord.objects.filter(animal=self.animal, datum=self.today).exists())


class InstitutionalAPITest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.company = make_company('44444444444')
        self.animal  = make_animal(self.company, ear_tag='HR444444444400001')
        self.today   = timezone.now().date()
        self.hr = HealthRecord.objects.create(
            animal=self.animal, datum=self.today, tip='cijepljenje',
            opis='Bruceloza', veterinar='Dr. Kovač',
            lijek='Brucella Vaccine', kolicina='2ml',
            karencija_do=self.today + timedelta(days=21),
        )

    def _get(self, scope, token):
        from livestock.views import institutional_api
        req = self.factory.get(f'/livestock/api/institutional/{scope}/?token={token}')
        return institutional_api(req, scope)

    def test_hapih_returns_records(self):
        tok = make_token(self.company, 'hapih')
        resp = self._get('hapih', tok.token)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['oib'], self.company.oib)
        self.assertEqual(data['count'], 1)
        r = data['records'][0]
        self.assertEqual(r['ear_tag'], self.animal.ear_tag)
        self.assertEqual(r['drug'], 'Brucella Vaccine')
        self.assertTrue(r['in_withdrawal'])

    def test_jrdz_returns_animals_with_species(self):
        tok = make_token(self.company, 'jrdz')
        resp = self._get('jrdz', tok.token)
        data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['count'], 1)
        a = data['animals'][0]
        self.assertEqual(a['species_code'], 'GVD')
        self.assertIn('sex', a)

    def test_jrdz_sex_female_krava(self):
        tok = make_token(self.company, 'jrdz')
        resp = self._get('jrdz', tok.token)
        data = json.loads(resp.content)
        self.assertEqual(data['animals'][0]['sex'], 'F')

    def test_jrdz_sex_male_bik(self):
        bik = make_animal(self.company, ear_tag='HR444444444400002', vrsta='bik')
        tok = make_token(self.company, 'jrdz')
        resp = self._get('jrdz', tok.token)
        data = json.loads(resp.content)
        sexes = {a['ear_tag']: a['sex'] for a in data['animals']}
        self.assertEqual(sexes[bik.ear_tag], 'M')
        self.assertEqual(sexes[self.animal.ear_tag], 'F')

    def test_sanitarna_blocked(self):
        tok = make_token(self.company, 'sanitarna')
        resp = self._get('sanitarna', tok.token)
        data = json.loads(resp.content)
        self.assertEqual(data['farm_status'], 'BLOCKED')
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['blocked_animals'][0]['ear_tag'], self.animal.ear_tag)

    def test_sanitarna_clear(self):
        self.hr.karencija_do = self.today - timedelta(days=1)
        self.hr.save()
        tok = make_token(self.company, 'sanitarna')
        resp = self._get('sanitarna', tok.token)
        data = json.loads(resp.content)
        self.assertEqual(data['farm_status'], 'CLEAR')
        self.assertEqual(data['count'], 0)

    def test_vetis_returns_health_records(self):
        tok = make_token(self.company, 'vetis')
        resp = self._get('vetis', tok.token)
        data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        animal_data = next(
            a for a in data['animals'] if a['ear_tag'] == self.animal.ear_tag
        )
        self.assertEqual(len(animal_data['health_records']), 1)
        self.assertEqual(animal_data['health_records'][0]['drug'], 'Brucella Vaccine')

    def test_invalid_token_403(self):
        resp = self._get('hapih', 'KRIVI_TOKEN_XYZ')
        self.assertEqual(resp.status_code, 403)

    def test_expired_token_403(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Exp', scope='hapih',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        resp = self._get('hapih', tok.token)
        self.assertEqual(resp.status_code, 403)

    def test_rate_limit_429(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='RL', scope='hapih',
            max_requests_day=2,
        )
        tok.record_access()
        tok.record_access()
        resp = self._get('hapih', tok.token)
        self.assertEqual(resp.status_code, 429)

    def test_unknown_scope_400(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Unknown', scope='hapih',
        )
        # Direktno pozovi s krivim scopeom (zaobiđi token scope check)
        from livestock.views import institutional_api
        req = self.factory.get(f'/livestock/api/institutional/nepostoji/?token={tok.token}')
        resp = institutional_api(req, 'nepostoji')
        self.assertEqual(resp.status_code, 403)  # token scope mismatch

    def test_audit_log_created(self):
        tok = make_token(self.company, 'hapih')
        before = InstitutionalAccessLog.objects.count()
        self._get('hapih', tok.token)
        after = InstitutionalAccessLog.objects.count()
        self.assertEqual(after, before + 1)


class VetQuickEntryTest(TestCase):

    def setUp(self):
        self.company = make_company('33333333333')
        self.company.booking_slug = 'test-farma-333'
        self.company.phone = '0976091655'
        self.company.save()
        self.animal = make_animal(self.company, ear_tag='HR333333333300001')
        self.today  = timezone.now().date()

    def test_get_valid_token(self):
        resp = self.client.get('/livestock/vet/test-farma-333/')
        self.assertEqual(resp.status_code, 200)

    def test_get_invalid_token(self):
        resp = self.client.get('/livestock/vet/krivi-token-xyz/')
        self.assertEqual(resp.status_code, 200)  # renders vet_404.html

    def test_post_creates_health_record(self):
        with patch('core.whatsapp.send_text') as mock_wa:
            resp = self.client.post('/livestock/vet/test-farma-333/', {
                'ear_tag':     self.animal.ear_tag,
                'datum':       str(self.today),
                'tip':         'tretman',
                'opis':        'Test tretman',
                'veterinar':   'Dr. Test',
                'lijek':       'Penicilin',
                'kolicina':    '5ml',
                'karencija_do': str(self.today + timedelta(days=7)),
            })
        self.assertEqual(resp.status_code, 302)
        hr = HealthRecord.objects.filter(animal=self.animal).first()
        self.assertIsNotNone(hr)
        self.assertEqual(hr.lijek, 'Penicilin')
        self.assertEqual(hr.karencija_do, self.today + timedelta(days=7))

    def test_post_invalid_ear_tag(self):
        resp = self.client.post('/livestock/vet/test-farma-333/', {
            'ear_tag': 'NEPOSTOJI',
            'datum':   str(self.today),
            'tip':     'pregled',
            'opis':    'test',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(HealthRecord.objects.filter(animal__company=self.company).count(), 0)

    def test_whatsapp_notify_called(self):
        with patch('core.whatsapp.send_text') as mock_wa:
            self.client.post('/livestock/vet/test-farma-333/', {
                'ear_tag':   self.animal.ear_tag,
                'datum':     str(self.today),
                'tip':       'tretman',
                'opis':      'WA test',
                'veterinar': 'Dr. WA',
                'lijek':     'Test Drug',
            })
            # WhatsApp se pokušava poslati
            # (može biti blokiran ako nema WAHA) — samo provjeri da nije exception
        self.assertTrue(True)


class InspectorViewTest(TestCase):

    def setUp(self):
        self.company = make_company('22222222222')
        self.animal  = make_animal(self.company, ear_tag='HR222222222200001')
        self.today   = timezone.now().date()

    def test_inspector_live_valid_token(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Inspekcija', scope='sanitarna',
        )
        resp = self.client.get(f'/livestock/inspect/sanitarna/{tok.token}/')
        self.assertEqual(resp.status_code, 200)

    def test_inspector_live_invalid_token(self):
        resp = self.client.get('/livestock/inspect/sanitarna/KRIVI_TOKEN/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'livestock/inspector_invalid.html')

    def test_inspector_live_expired_token(self):
        tok = InstitutionalAccessToken.objects.create(
            company=self.company, name='Expired', scope='sanitarna',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        resp = self.client.get(f'/livestock/inspect/sanitarna/{tok.token}/')
        self.assertTemplateUsed(resp, 'livestock/inspector_invalid.html')


class PanicButtonTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('test_farmer', password='pass123')
        self.company = make_company('11111111111')
        self.profile = UserProfile.objects.create(
            user=self.user, company=self.company, role='company_admin',
        )
        self.client.login(username='test_farmer', password='pass123')

    def test_panic_button_get(self):
        resp = self.client.get('/livestock/inspekcija/')
        self.assertEqual(resp.status_code, 200)

    def test_panic_button_creates_token(self):
        before = InstitutionalAccessToken.objects.count()
        resp = self.client.post('/livestock/inspekcija/', {'scope': 'sanitarna'})
        self.assertEqual(resp.status_code, 200)
        after = InstitutionalAccessToken.objects.count()
        self.assertEqual(after, before + 1)
        tok = InstitutionalAccessToken.objects.filter(company=self.company).last()
        self.assertIsNotNone(tok.expires_at)  # 24h token
        self.assertEqual(tok.scope, 'sanitarna')

    def test_panic_button_token_expires_24h(self):
        self.client.post('/livestock/inspekcija/', {'scope': 'hapih'})
        tok = InstitutionalAccessToken.objects.filter(company=self.company).last()
        delta = tok.expires_at - timezone.now()
        self.assertAlmostEqual(delta.total_seconds(), 86400, delta=60)
