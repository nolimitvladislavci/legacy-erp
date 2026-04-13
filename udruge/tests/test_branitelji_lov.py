import random
"""
Testovi za branitelji + lov module.
Pokretanje: venv/bin/python manage.py test udruge.tests.test_branitelji_lov -v2
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch

from companies.models import Company
from udruge.models import (
    Clan, StatusBranitelja, OdlikovanjeBranitelja,
    Loviste, LovackaIskaznica, DopustenjeLova, ZapisnikLova, Trofej,
)

User = get_user_model()


class BraniteljiModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='DVD Test', oib='1' + str(random.randint(1000000000, 9999999999)))
        self.clan = Clan.objects.create(
            company=self.company, first_name='Ivan', last_name='Horvat',
            status='aktivan', membership_type='redovni',
        )

    def test_status_branitelja_create(self):
        sb = StatusBranitelja.objects.create(
            clan=self.clan, vrsta_statusa='hrvi_2',
            postrojba='HV', naziv_postrojbe='204. vukovarska brigada',
            dana_sudjelovanja=365, borbeni_sektor=True,
            postotak_invalidnosti=70,
        )
        self.assertTrue(sb.je_hrvi)
        self.assertIn('HRVI', str(sb))

    def test_hrvi_detection(self):
        sb = StatusBranitelja.objects.create(clan=self.clan, vrsta_statusa='branitelj')
        self.assertFalse(sb.je_hrvi)
        sb.vrsta_statusa = 'hrvi_1'
        sb.save()
        self.assertTrue(sb.je_hrvi)

    def test_odlikovanje_create(self):
        od = OdlikovanjeBranitelja.objects.create(
            clan=self.clan, vrsta='red_danice_hr',
            naziv='Red Danice Hrvatske', broj_odluke='NN-123/2000',
        )
        self.assertEqual(od.vrsta, 'red_danice_hr')

    def test_one_to_one_constraint(self):
        StatusBranitelja.objects.create(clan=self.clan, vrsta_statusa='branitelj')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            StatusBranitelja.objects.create(clan=self.clan, vrsta_statusa='dragovoljac')


class LovModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='LD Jelen', oib='2' + str(random.randint(1000000000, 9999999999)))
        self.clan = Clan.objects.create(
            company=self.company, first_name='Marko', last_name='Lovac',
            status='aktivan',
        )
        self.loviste = Loviste.objects.create(
            company=self.company, naziv='Bilogora I',
            povrsina_ha=Decimal('1500.00'), vrsta='zajednicko',
        )

    def test_loviste_str(self):
        self.assertIn('Bilogora', str(self.loviste))
        self.assertIn('1500', str(self.loviste))

    def test_iskaznica_aktivna(self):
        from django.utils import timezone
        from datetime import timedelta
        isk = LovackaIskaznica.objects.create(
            company=self.company, clan=self.clan,
            broj_iskaznice='HR-12345',
            datum_izdavanja=timezone.now().date(),
            vrijedi_do=timezone.now().date() + timedelta(days=365*5),
            markica_godina=timezone.now().year if timezone.now().month >= 4 else timezone.now().year - 1,
        )
        self.assertTrue(isk.je_aktivna)
        self.assertFalse(isk.treba_markicu)

    def test_iskaznica_istekla(self):
        from django.utils import timezone
        from datetime import timedelta
        isk = LovackaIskaznica.objects.create(
            company=self.company, clan=self.clan,
            broj_iskaznice='HR-99999',
            datum_izdavanja=timezone.now().date() - timedelta(days=365*6),
            vrijedi_do=timezone.now().date() - timedelta(days=1),
        )
        self.assertFalse(isk.je_aktivna)

    def test_iskaznica_treba_markicu(self):
        from django.utils import timezone
        from datetime import timedelta
        isk = LovackaIskaznica.objects.create(
            company=self.company, clan=self.clan,
            broj_iskaznice='HR-55555',
            datum_izdavanja=timezone.now().date(),
            vrijedi_do=timezone.now().date() + timedelta(days=365*5),
            markica_godina=2020,  # stara markica
        )
        self.assertTrue(isk.treba_markicu)

    def test_dopustenje_create(self):
        d = DopustenjeLova.objects.create(
            company=self.company, loviste=self.loviste, clan=self.clan,
            broj_dopustenja='DP-001/2026',
            datum_lova='2026-03-26', vrsta_divljaci='Srna',
            broj_komada=1,
        )
        self.assertIn('Srna', str(d))

    def test_zapisnik_create(self):
        z = ZapisnikLova.objects.create(
            company=self.company, loviste=self.loviste, clan=self.clan,
            datum='2026-03-26', nacin_lova='pojedinacni',
            vrsta_divljaci='Divlja svinja', spol='muz',
            masa_kg=Decimal('85.50'),
        )
        self.assertIn('Divlja svinja', str(z))

    def test_trofej_s_medaljom(self):
        z = ZapisnikLova.objects.create(
            company=self.company, loviste=self.loviste, clan=self.clan,
            datum='2026-03-26', vrsta_divljaci='Jelen',
        )
        t = Trofej.objects.create(
            company=self.company, clan=self.clan, zapisnik=z,
            vrsta='jelen_paroske', cis_tockova=Decimal('195.50'),
            medalja='zlato',
        )
        self.assertEqual(t.medalja, 'zlato')
        self.assertIn('Jelenje', str(t))

    def test_cross_tenant_isolation(self):
        """Firma A ne vidi lovista firme B."""
        company_b = Company.objects.create(name='LD Fazan', oib='3' + str(random.randint(1000000000, 9999999999)))
        Loviste.objects.create(company=company_b, naziv='Papuk II', povrsina_ha=Decimal('800'))
        # Firma A query
        lovista_a = Loviste.objects.filter(company=self.company)
        self.assertEqual(lovista_a.count(), 1)
        self.assertEqual(lovista_a.first().naziv, 'Bilogora I')


class BraniteljiViewTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='HVIDRA Test', oib='4' + str(random.randint(1000000000, 9999999999)))
        self.user = User.objects.create_user('testbran', password='Test1234!')
        self.user.is_staff = True
        self.user.save()

    @patch('core.company_utils.get_user_company')
    def test_dashboard_renders(self, mock_gc):
        mock_gc.return_value = self.company
        self.client.force_login(self.user)
        resp = self.client.get(reverse('udruge:branitelji_dashboard'), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)

    @patch('core.company_utils.get_user_company')
    def test_status_create_flow(self, mock_gc):
        mock_gc.return_value = self.company
        self.client.force_login(self.user)
        clan = Clan.objects.create(
            company=self.company, first_name='Pero', last_name='Perić', status='aktivan',
        )
        resp = self.client.post(reverse('udruge:branitelj_status_create', args=[clan.pk]), {
            'vrsta_statusa': 'hrvi_3',
            'postrojba': 'HV',
            'dana_sudjelovanja': '180',
            'borbeni_sektor': 'on',
        })
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(StatusBranitelja.objects.filter(clan=clan).exists())
        sb = clan.status_branitelja
        self.assertTrue(sb.borbeni_sektor)
        self.assertEqual(sb.dana_sudjelovanja, 180)


class LovViewTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='LD Test', oib='5' + str(random.randint(1000000000, 9999999999)))
        self.user = User.objects.create_user('testlov', password='Test1234!')
        self.user.is_staff = True
        self.user.save()

    @patch('core.company_utils.get_user_company')
    def test_lov_dashboard_renders(self, mock_gc):
        mock_gc.return_value = self.company
        self.client.force_login(self.user)
        resp = self.client.get(reverse('udruge:lov_dashboard'), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)

    @patch('core.company_utils.get_user_company')
    def test_loviste_crud(self, mock_gc):
        mock_gc.return_value = self.company
        self.client.force_login(self.user)
        # Create
        resp = self.client.post(reverse('udruge:loviste_create'), {
            'naziv': 'Baranja Zapad',
            'povrsina_ha': '2500.00',
            'vrsta': 'zajednicko',
        })
        self.assertIn(resp.status_code, [200, 301, 302])
        lov = Loviste.objects.get(company=self.company)
        self.assertEqual(lov.naziv, 'Baranja Zapad')
        # Edit
        resp2 = self.client.post(reverse('udruge:loviste_edit', args=[lov.pk]), {
            'naziv': 'Baranja Zapad (revidirano)',
            'povrsina_ha': '2600.00',
            'vrsta': 'zajednicko',
        })
        self.assertIn(resp2.status_code, [200, 301, 302])
        lov.refresh_from_db()
        self.assertIn('revidirano', lov.naziv)

    @patch('core.company_utils.get_user_company')
    def test_dopustenje_create(self, mock_gc):
        mock_gc.return_value = self.company
        self.client.force_login(self.user)
        loviste = Loviste.objects.create(company=self.company, naziv='Test', povrsina_ha=100)
        clan = Clan.objects.create(company=self.company, first_name='A', last_name='B', status='aktivan')
        resp = self.client.post(reverse('udruge:lov_dopustenje_create'), {
            'loviste': loviste.pk, 'clan': clan.pk,
            'broj_dopustenja': 'DP-001',
            'datum_lova': '2026-04-01',
            'vrsta_divljaci': 'Fazan',
            'broj_komada': '3',
        })
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(DopustenjeLova.objects.filter(company=self.company).count(), 1)
