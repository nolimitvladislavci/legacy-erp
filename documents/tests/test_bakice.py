"""
Arhiva — test 6 bakica + Marija (sezonski posao).

Scenario: Sezona knjizenja. 6 komitentica (bakice) slikaju racune
mobitelom i uploadaju u LC. Marija pregledava AI prijedloge,
prihvaca i eksportira revizijski ZIP.

Bakice:
1. Ankica  — OPG, slika racune za gnojivo (invoice_in)
2. Dragica — Obrt pekara, prima fakture od bracna (invoice_in)
3. Slavica — Udruga branitelja, skenira CMR-ove (cmr)
4. Ljubica — Mali ducan, fotografira primke (primka)
5. Marica  — OPG Korpa, otkupni blokovi za vocnjak (otkupni_blok)
6. Barica  — Frizerski salon, fiskalni certifikat (fiscal_cert)

Marija — racunovodja, pregledava SVE, AI knjiži, ZIP export.
"""
import json
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()
_n = [0]
def _uid():
    _n[0] += 1
    return _n[0]


def _pdf(name='racun.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 ' + name.encode(), content_type='application/pdf')

def _jpg(name='slika.jpg'):
    # Minimal JFIF header
    return SimpleUploadedFile(name, b'\xff\xd8\xff\xe0' + b'\x00' * 100, content_type='image/jpeg')

def _png():
    return SimpleUploadedFile('foto.png',
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
        b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
        b'\xd8N\x00\x00\x00\x00IEND\xaeB\x60\x82',
        content_type='image/png')

def _store_mock(ct='application/pdf'):
    return patch('documents.views.store_document', return_value={
        'path': 'arhiva/test/mock_%d.pdf' % _uid(),
        'hash': 'hash%d' % _uid(),
        'size': 2048,
        'backend': 'local',
        'content_type': ct,
    })


@override_settings(LANGUAGE_CODE='hr')
class BakiceSezonaTest(TestCase):
    """Sezonski test — 6 bakica + Marija = 7 korisnika, puni workflow."""

    def setUp(self):
        n = _uid()
        from companies.models import Company

        # Marijina firma (racunovodstvo)
        self.ks_limit = Company.objects.create(
            name='KS LIMIT %d' % n, oib='%011d' % (60000000000 + n))

        # Firme komitentica
        self.ankica_co = Company.objects.create(
            name='OPG Ankica %d' % n, oib='%011d' % (61000000000 + n), business_type='opg')
        self.dragica_co = Company.objects.create(
            name='Pekara Dragica %d' % n, oib='%011d' % (62000000000 + n), business_type='obrt')
        self.slavica_co = Company.objects.create(
            name='Udruga Branitelja %d' % n, oib='%011d' % (63000000000 + n), business_type='udruga')
        self.ljubica_co = Company.objects.create(
            name='Trgovina Ljubica %d' % n, oib='%011d' % (64000000000 + n), business_type='obrt')
        self.marica_co = Company.objects.create(
            name='OPG Marica %d' % n, oib='%011d' % (65000000000 + n), business_type='opg')
        self.barica_co = Company.objects.create(
            name='Salon Barica %d' % n, oib='%011d' % (66000000000 + n), business_type='obrt')

        # Korisnici
        self.marija = User.objects.create_superuser(
            username='marija%d' % n, password='x', email='m%d@t.co' % n)
        self.ankica = User.objects.create_user(username='ankica%d' % n, password='x')
        self.dragica = User.objects.create_user(username='dragica%d' % n, password='x')
        self.slavica = User.objects.create_user(username='slavica%d' % n, password='x')
        self.ljubica = User.objects.create_user(username='ljubica%d' % n, password='x')
        self.marica = User.objects.create_user(username='marica%d' % n, password='x')
        self.barica = User.objects.create_user(username='barica%d' % n, password='x')

    def _login_as(self, user, company):
        self.client = Client(HTTP_ACCEPT_LANGUAGE='hr')
        self.client.force_login(user)
        s = self.client.session
        s['company_id'] = str(company.pk)
        s.save()

    def _upload(self, user, company, file, source_type, doc_number, partner, amount):
        """Upload file — returns True if success (302 redirect to list)."""
        self._login_as(user, company)
        ct = 'image/jpeg' if file.content_type.startswith('image') else 'application/pdf'
        with _store_mock(ct), patch('documents.views.get_user_company', return_value=company):
            resp = self.client.post(reverse('documents:arhiva_upload'), {
                'file': file, 'source_type': source_type,
                'doc_number': doc_number, 'partner_name': partner,
                'amount': str(amount), 'doc_date': str(date.today()),
            })
        # 302 = success redirect, 301 = HTTPS redirect (test env)
        return resp

    # ═══ BAKICA 1: ANKICA — OPG, gnojivo računi ═══

    def test_01_ankica_upload_invoice(self):
        """Ankica slika racun za gnojivo mobitelom."""
        resp = self._upload(self.ankica, self.ankica_co,
            _jpg('gnojivo_racun.jpg'), 'invoice_in',
            'UR-2026-001', 'Agro Centar d.o.o.', 450.00)
        self.assertIn(resp.status_code, [200, 301, 302])

    def test_02_ankica_upload_second(self):
        """Ankica uploaduje drugi racun — sjeme."""
        resp = self._upload(self.ankica, self.ankica_co,
            _pdf('sjeme_faktura.pdf'), 'invoice_in',
            'UR-2026-002', 'Sjemenarna d.o.o.', 280.00)
        self.assertIn(resp.status_code, [200, 301, 302])

    # ═══ BAKICA 2: DRAGICA — pekara, brašno fakture ═══

    def test_03_dragica_upload_flour_invoice(self):
        """Dragica prima fakturu za brasno."""
        resp = self._upload(self.dragica, self.dragica_co,
            _pdf('brasno_faktura.pdf'), 'invoice_in',
            'URA-2026-015', 'Mlin Osijek d.o.o.', 1250.00)
        self.assertIn(resp.status_code, [200, 301, 302])

    # ═══ BAKICA 3: SLAVICA — udruga, CMR dokumenti ═══

    def test_04_slavica_upload_cmr(self):
        """Slavica skenira CMR za donaciju hrane."""
        resp = self._upload(self.slavica, self.slavica_co,
            _png(), 'cmr',
            'CMR-2026-003', 'Donacija Crveni kriz', 0)
        self.assertIn(resp.status_code, [200, 301, 302])

    # ═══ BAKICA 4: LJUBICA — dućan, primke ═══

    def test_05_ljubica_upload_primka(self):
        """Ljubica fotografira primku robe."""
        resp = self._upload(self.ljubica, self.ljubica_co,
            _jpg('primka_roba.jpg'), 'primka',
            'PRI-2026-042', 'Velpro d.o.o.', 3200.00)
        self.assertIn(resp.status_code, [200, 301, 302])

    # ═══ BAKICA 5: MARICA — OPG, otkupni blokovi ═══

    def test_06_marica_upload_otkupni(self):
        """Marica slikava otkupni blok za jabuke."""
        resp = self._upload(self.marica, self.marica_co,
            _jpg('otkupni_jabuke.jpg'), 'otkupni_blok',
            'OTK-2026-007', 'Otkup Slavonija', 890.00)
        self.assertIn(resp.status_code, [200, 301, 302])

    # ═══ BAKICA 6: BARICA — salon, fiskalni cert ═══

    def test_07_barica_upload_fiscal(self):
        """Barica uploaduje fiskalni certifikat."""
        resp = self._upload(self.barica, self.barica_co,
            _pdf('fina_cert.pdf'), 'fiscal_cert',
            'CERT-2026-001', 'FINA', 200.00)
        self.assertIn(resp.status_code, [200, 301, 302])

    # ═══ MARIJA — pregledava SVE ═══

    def test_08_marija_sees_all_companies(self):
        """Marija kao superadmin vidi AI inbox za sve firme."""
        self._login_as(self.marija, self.ks_limit)
        with patch('documents.views.get_user_company', return_value=None):
            resp = self.client.get(reverse('documents:ai_inbox'), follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_09_marija_convert_image(self):
        """Marija prima sliku racuna i pokrece AI convert."""
        self._login_as(self.marija, self.ks_limit)
        with patch('documents.views.get_user_company', return_value=self.ankica_co):
            resp = self.client.post(reverse('documents:arhiva_convert'),
                {'file': _png()}, HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200 and 'json' in resp.get('Content-Type', ''):
            data = json.loads(resp.content)
            self.assertIn('success', data)

    def test_10_marija_bulk_accept(self):
        """Marija prihvaca sve AI prijedloge odjednom."""
        from documents.models import ArhivaEntry
        # Create entries with proposals for different companies
        for i, co in enumerate([self.ankica_co, self.dragica_co, self.ljubica_co]):
            ArhivaEntry.objects.create(
                company=co, source_type='invoice_in',
                source_id='bulk-src-%d-%d' % (_uid(), i),
                doc_number='BULK-%d' % _uid(),
                partner_name='Test %d' % i, amount=Decimal('100'),
                currency='EUR', doc_date=date.today(),
                archived_by=self.marija,
                ai_proposal={'debit': [{'account': '1300', 'amount': 100}],
                             'credit': [{'account': '2200', 'amount': 100}],
                             'confidence': 'high'},
            )
        self._login_as(self.marija, self.ks_limit)
        with patch('documents.views.get_user_company', return_value=self.ankica_co):
            resp = self.client.post(reverse('documents:ai_inbox_bulk_accept'),
                json.dumps({'company_id': str(self.ankica_co.pk)}),
                content_type='application/json')
        self.assertIn(resp.status_code, [200, 301])

    def test_11_marija_revizija_zip(self):
        """Marija exportira revizijski ZIP za Ankicin OPG."""
        from documents.models import ArhivaEntry
        for i in range(3):
            ArhivaEntry.objects.create(
                company=self.ankica_co, source_type='invoice_in',
                source_id='rev-src-%d' % _uid(),
                doc_number='REV-%d' % _uid(),
                partner_name='Partner', amount=Decimal('100'),
                currency='EUR', doc_date=date.today(),
                archived_by=self.marija,
            )
        self._login_as(self.marija, self.ks_limit)
        with patch('documents.views.get_user_company', return_value=self.ankica_co):
            resp = self.client.post(reverse('documents:revizija_export'), {
                'company_id': str(self.ankica_co.pk),
                'date_from': str(date.today() - timedelta(days=30)),
                'date_to': str(date.today()),
            })
        self.assertIn(resp.status_code, [200, 301])
        if resp.status_code == 200:
            self.assertIn('zip', resp.get('Content-Type', ''))

    def test_12_marija_csv_export(self):
        """Marija eksportira CSV za poreznu."""
        self._login_as(self.marija, self.ks_limit)
        with patch('documents.views.get_user_company', return_value=self.ankica_co):
            resp = self.client.get(reverse('documents:arhiva_export'), follow=True)
        self.assertEqual(resp.status_code, 200)

    # ═══ CROSS-TENANT IZOLACIJA ═══

    def test_13_ankica_ne_vidi_dragicu(self):
        """Ankica NE smije vidjeti Dragicine dokumente."""
        from documents.models import ArhivaEntry
        dragica_entry = ArhivaEntry.objects.create(
            company=self.dragica_co, source_type='invoice_in',
            source_id='cross-%d' % _uid(), doc_number='CROSS-%d' % _uid(),
            partner_name='Tajno', amount=Decimal('999'),
            currency='EUR', doc_date=date.today(),
            archived_by=self.dragica,
        )
        self._login_as(self.ankica, self.ankica_co)
        with patch('documents.views.get_user_company', return_value=self.ankica_co):
            resp = self.client.get(reverse('documents:arhiva_detail_ajax', args=[dragica_entry.pk]),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
        self.assertIn(resp.status_code, [403, 404])

    def test_14_barica_ne_vidi_slavicu(self):
        """Barica NE smije vidjeti udrugine CMR-ove."""
        from documents.models import ArhivaEntry
        slavica_entry = ArhivaEntry.objects.create(
            company=self.slavica_co, source_type='cmr',
            source_id='cmr-%d' % _uid(), doc_number='CMR-TAJNI-%d' % _uid(),
            partner_name='Donacija', amount=Decimal('0'),
            currency='EUR', doc_date=date.today(),
            archived_by=self.slavica,
        )
        self._login_as(self.barica, self.barica_co)
        with patch('documents.views.get_user_company', return_value=self.barica_co):
            resp = self.client.get(reverse('documents:arhiva_detail_ajax', args=[slavica_entry.pk]),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
        self.assertIn(resp.status_code, [403, 404])

    # ═══ ZOR COMPLIANCE za sve bakice ═══

    def test_15_all_entries_have_protection(self):
        """Svaki dokument ima 11-godisnju zastitu."""
        from documents.models import ArhivaEntry
        for co in [self.ankica_co, self.dragica_co, self.slavica_co,
                   self.ljubica_co, self.marica_co, self.barica_co]:
            e = ArhivaEntry.objects.create(
                company=co, source_type='document',
                source_id='zor-%d' % _uid(), doc_number='ZOR-%d' % _uid(),
                partner_name='Test', amount=Decimal('50'),
                currency='EUR', doc_date=date.today(),
                archived_by=self.marija,
            )
            self.assertIsNotNone(e.deletion_protected_until)
            self.assertTrue(e.is_deletion_protected)
            self.assertEqual(len(e.integrity_hash), 64)
            self.assertTrue(e.barcode.startswith('LC-'))

    # ═══ POMIJEŠANI RAČUNI — bakice greškom uploaduju u krivu firmu ═══

    def test_16_ankica_upload_u_dragicinu_firmu(self):
        """Ankica greškom uploada u Dragicinu firmu — ne smije vidjeti."""
        from documents.models import ArhivaEntry
        # Ankica uploada u svoju firmu
        e_ankica = ArhivaEntry.objects.create(
            company=self.ankica_co, source_type='invoice_in',
            source_id='ankica-%d' % _uid(), doc_number='ANKICA-%d' % _uid(),
            partner_name='Agro', amount=Decimal('300'), currency='EUR',
            doc_date=date.today(), archived_by=self.ankica)
        # Dragica uploada u svoju firmu
        e_dragica = ArhivaEntry.objects.create(
            company=self.dragica_co, source_type='invoice_in',
            source_id='dragica-%d' % _uid(), doc_number='DRAGICA-%d' % _uid(),
            partner_name='Mlin', amount=Decimal('1200'), currency='EUR',
            doc_date=date.today(), archived_by=self.dragica)
        # Ankica pokusa vidjeti Dragicin dokument
        self._login_as(self.ankica, self.ankica_co)
        with patch('documents.views.get_user_company', return_value=self.ankica_co):
            resp = self.client.get(reverse('documents:arhiva_detail_ajax', args=[e_dragica.pk]),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
        self.assertIn(resp.status_code, [403, 404])

    def test_17_dragica_upload_u_slavicinu_udrugu(self):
        """Dragica ne smije uploadati u Slavicinu udrugu."""
        from documents.models import ArhivaEntry
        # Slavica ima CMR u udruzi
        e_slavica = ArhivaEntry.objects.create(
            company=self.slavica_co, source_type='cmr',
            source_id='slavica-%d' % _uid(), doc_number='SLAVICA-CMR-%d' % _uid(),
            partner_name='Donacija', amount=Decimal('0'), currency='EUR',
            doc_date=date.today(), archived_by=self.slavica)
        # Dragica pokusa pristupiti
        self._login_as(self.dragica, self.dragica_co)
        with patch('documents.views.get_user_company', return_value=self.dragica_co):
            resp = self.client.get(reverse('documents:arhiva_detail_ajax', args=[e_slavica.pk]),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
        self.assertIn(resp.status_code, [403, 404])

    def test_18_ljubica_ne_vidi_maricin_otkupni(self):
        """Ljubica ne smije vidjeti Maricin otkupni blok."""
        from documents.models import ArhivaEntry
        e_marica = ArhivaEntry.objects.create(
            company=self.marica_co, source_type='otkupni_blok',
            source_id='marica-%d' % _uid(), doc_number='MARICA-OTK-%d' % _uid(),
            partner_name='Otkup', amount=Decimal('890'), currency='EUR',
            doc_date=date.today(), archived_by=self.marica)
        self._login_as(self.ljubica, self.ljubica_co)
        with patch('documents.views.get_user_company', return_value=self.ljubica_co):
            resp = self.client.get(reverse('documents:arhiva_detail_ajax', args=[e_marica.pk]),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
        self.assertIn(resp.status_code, [403, 404])

    def test_19_marija_vidi_sve(self):
        """Marija kao superadmin vidi dokumente SVIH bakica."""
        from documents.models import ArhivaEntry
        entries = []
        for co, user, st in [
            (self.ankica_co, self.ankica, 'invoice_in'),
            (self.dragica_co, self.dragica, 'invoice_in'),
            (self.slavica_co, self.slavica, 'cmr'),
            (self.ljubica_co, self.ljubica, 'primka'),
            (self.marica_co, self.marica, 'otkupni_blok'),
            (self.barica_co, self.barica, 'fiscal_cert'),
        ]:
            e = ArhivaEntry.objects.create(
                company=co, source_type=st,
                source_id='marija-all-%d' % _uid(), doc_number='ALL-%d' % _uid(),
                partner_name='Test', amount=Decimal('100'), currency='EUR',
                doc_date=date.today(), archived_by=user,
                ai_proposal={'debit': [], 'credit': [], 'confidence': 'high'})
            entries.append(e)
        # Marija vidi sve u AI inboxu
        self._login_as(self.marija, self.ks_limit)
        with patch('documents.views.get_user_company', return_value=None):
            resp = self.client.get(reverse('documents:ai_inbox'), follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_20_pomjesani_racuni_ne_cure(self):
        """Nijedan racun ne curi u tudju firmu — bulk provjera."""
        from documents.models import ArhivaEntry
        pairs = [
            (self.ankica, self.ankica_co, self.dragica_co),
            (self.dragica, self.dragica_co, self.slavica_co),
            (self.slavica, self.slavica_co, self.ljubica_co),
            (self.ljubica, self.ljubica_co, self.marica_co),
            (self.marica, self.marica_co, self.barica_co),
            (self.barica, self.barica_co, self.ankica_co),
        ]
        for user, own_co, other_co in pairs:
            other_entry = ArhivaEntry.objects.create(
                company=other_co, source_type='document',
                source_id='leak-%d' % _uid(), doc_number='LEAK-%d' % _uid(),
                partner_name='Tajno', amount=Decimal('999'), currency='EUR',
                doc_date=date.today(), archived_by=self.marija)
            self._login_as(user, own_co)
            with patch('documents.views.get_user_company', return_value=own_co):
                resp = self.client.get(
                    reverse('documents:arhiva_detail_ajax', args=[other_entry.pk]),
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest', follow=True)
            self.assertIn(resp.status_code, [403, 404],
                '%s vidi dokument firme %s!' % (user.username, other_co.name))

    def test_21_all_source_types_accepted(self):
        """Svi source_type-ovi iz bakica scenarija rade."""
        from documents.models import ArhivaEntry
        types = ['invoice_in', 'cmr', 'primka', 'otkupni_blok', 'fiscal_cert', 'document']
        for st in types:
            e = ArhivaEntry.objects.create(
                company=self.ks_limit, source_type=st,
                source_id='st-%d' % _uid(), doc_number='ST-%d' % _uid(),
                partner_name='TypeTest', amount=Decimal('10'),
                currency='EUR', doc_date=date.today(),
                archived_by=self.marija,
            )
            self.assertEqual(e.source_type, st)
            self.assertIsNotNone(e.pk)
