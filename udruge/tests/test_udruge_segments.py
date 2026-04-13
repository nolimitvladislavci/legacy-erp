"""
Udruge segmenti testovi — DVD, KUD, Ribari, Pčelari, Rakija, Voćari.
Min 30 testova za sve segmente.
"""
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
_n = [1000]


def _uid():
    _n[0] += 1
    return _n[0]


@override_settings(LANGUAGE_CODE='hr')
class UdrugeSegmentsTest(TestCase):
    """Testovi za 6 sektorskih segmenata udruge modula."""

    def setUp(self):
        n = _uid()
        from companies.models import Company
        self.company = Company.objects.create(
            name='Udruga Seg %d' % n,
            oib='%011d' % (60000000000 + n),
            business_type='udruga',
        )
        self.user = User.objects.create_user(username='seg%d' % n, password='x')
        self.client = Client(HTTP_ACCEPT_LANGUAGE='hr')
        self.client.force_login(self.user)
        s = self.client.session
        s['company_id'] = str(self.company.pk)
        s.save()

    def _clan(self, **kw):
        from udruge.models import Clan
        n = _uid()
        d = dict(
            company=self.company,
            first_name='Ime%d' % n,
            last_name='Prezime%d' % n,
            oib='%011d' % (70000000000 + n),
            date_joined=date.today(),
        )
        d.update(kw)
        return Clan.objects.create(**d)

    def _sekcija(self, **kw):
        from udruge.models import Sekcija
        n = _uid()
        d = dict(company=self.company, name='Sekcija %d' % n)
        d.update(kw)
        return Sekcija.objects.create(**d)

    # ═══════════════════════════════════════════════════════════════
    # DVD — DOBROVOLJNO VATROGASNO DRUŠTVO
    # ═══════════════════════════════════════════════════════════════

    def test_01_dvd_create_oprema(self):
        """Kreiranje vatrogasne opreme."""
        from udruge.models import VatrogasnaOprema
        oprema = VatrogasnaOprema.objects.create(
            company=self.company,
            naziv='Aparat S-9 9kg',
            kategorija='aparat',
            serijski_broj='INV-001',
            status='ispravno',
            atest_vrijedi_do=date.today() + timedelta(days=365),
        )
        self.assertIsNotNone(oprema.pk)
        self.assertEqual(oprema.status, 'ispravno')
        self.assertEqual(oprema.kategorija, 'aparat')

    def test_02_dvd_create_vozilo(self):
        """Kreiranje vatrogasnog vozila."""
        from udruge.models import VatrogasnoVozilo
        vozilo = VatrogasnoVozilo.objects.create(
            company=self.company,
            naziv='Navalno vozilo NV-1',
            tip='navalno',
            reg_oznaka='OS-123-AB',
            godina_proizvodnje=2015,
            status='aktivno',
        )
        self.assertIsNotNone(vozilo.pk)
        self.assertEqual(vozilo.tip, 'navalno')
        self.assertIn('NV-1', str(vozilo))

    def test_03_dvd_create_intervencija(self):
        """Kreiranje intervencije s sudionicima."""
        from udruge.models import Intervencija
        clan = self._clan()
        interv = Intervencija.objects.create(
            company=self.company,
            tip='pozar',
            alarm_primljen=timezone.now(), evidencijski_broj='INT-2026-001',
            povratak=timezone.now() + timedelta(hours=3),
            lokacija='Šuma Čepinska',
            opis='Požar niske vegetacije',
            voditelj=clan,
        )
        interv.sudionici.add(clan)
        self.assertIsNotNone(interv.pk)
        self.assertEqual(interv.sudionici.count(), 1)

    def test_04_dvd_create_vjezba(self):
        """Kreiranje vatrogasne vježbe."""
        from udruge.models import Vjezba
        clan = self._clan()
        vjezba = Vjezba.objects.create(
            company=self.company,
            naziv='Taktička vježba gašenja',
            tip='prakticna',
            datum=date.today(),
            trajanje_sati=Decimal('3.0'),
            lokacija='Vatrogasni dom',
            voditelj=clan,
        )
        vjezba.sudionici.add(clan)
        self.assertIsNotNone(vjezba.pk)
        self.assertEqual(vjezba.tip, 'prakticna')
        self.assertEqual(vjezba.sudionici.count(), 1)

    def test_05_dvd_create_zvanje(self):
        """Kreiranje vatrogasnog zvanja."""
        from udruge.models import VatrogasnoZvanje
        clan = self._clan()
        zvanje = VatrogasnoZvanje.objects.create(
            clan=clan,
            razina='A',
            naziv_zvanja='Vatrogasac',
            datum_stjecanja=date.today() - timedelta(days=365),
            izdavac='HVZ',
        )
        self.assertIsNotNone(zvanje.pk)
        self.assertIn('Vatrogasac', str(zvanje))

    def test_06_dvd_atest_expiry_check(self):
        """Provjera da atest_expiry task prepoznaje isteklu opremu."""
        from udruge.models import VatrogasnaOprema
        # Oprema s atestom koji ističe za 10 dana
        VatrogasnaOprema.objects.create(
            company=self.company,
            naziv='Cijev B-75',
            kategorija='cijev',
            status='ispravno',
            atest_vrijedi_do=date.today() + timedelta(days=10),
        )
        # Oprema s isteklim atestom
        VatrogasnaOprema.objects.create(
            company=self.company,
            naziv='Cijev C-52',
            kategorija='cijev',
            status='ispravno',
            atest_vrijedi_do=date.today() - timedelta(days=5),
        )
        from udruge.tasks import check_vatrogasna_oprema_atesti
        result = check_vatrogasna_oprema_atesti()
        self.assertGreaterEqual(result['expiring_30d'], 1)
        self.assertGreaterEqual(result['expired_marked'], 1)

    # ═══════════════════════════════════════════════════════════════
    # KUD — KULTURNO-UMJETNIČKO DRUŠTVO
    # ═══════════════════════════════════════════════════════════════

    def test_07_kud_create_repertoar(self):
        """Kreiranje repertoara."""
        from udruge.models import Repertoar
        sekcija = self._sekcija()
        rep = Repertoar.objects.create(
            company=self.company,
            sekcija=sekcija,
            naziv='Kolo iz Slavonije',
            tip='ples',
            autor='Narodni',
            trajanje_min=5,
            region='Slavonija',
        )
        self.assertIsNotNone(rep.pk)
        self.assertIn('Kolo', str(rep))

    def test_08_kud_create_proba(self):
        """Kreiranje probe s prisutnosti."""
        from udruge.models import ProbaLog
        sekcija = self._sekcija()
        clan1 = self._clan()
        clan2 = self._clan()
        proba = ProbaLog.objects.create(
            company=self.company,
            sekcija=sekcija,
            datum=date.today(),
            pocetak=timezone.now().time(),
            lokacija='Dvorana KUD-a',
            voditelj=clan1,
        )
        proba.prisutni.add(clan1, clan2)
        self.assertEqual(proba.prisutni_count, 2)

    def test_09_kud_create_kostim(self):
        """Kreiranje kostima s dodjelom članu."""
        from udruge.models import Kostim
        clan = self._clan()
        kostim = Kostim.objects.create(
            company=self.company,
            naziv='Slavonska nošnja',
            spol='Z',
            velicina='M',
            inventarni_broj='K-001',
            dodijeljen_clanu=clan,
            dodijeljen_od=date.today(),
            stanje='novo',
            nabavna_cijena=Decimal('250.00'),
        )
        self.assertIsNotNone(kostim.pk)
        self.assertIn(str(clan), str(kostim))

    def test_10_kud_nastup_plan(self):
        """Kreiranje plana nastupa vezan na dogadjaj."""
        from udruge.models import Dogadjaj, NastupPlan
        dogadjaj = Dogadjaj.objects.create(
            company=self.company,
            name='Festival folklora',
            event_type='festival',
            start_date=timezone.now() + timedelta(days=30),
            status='planned',
        )
        plan = NastupPlan.objects.create(
            dogadjaj=dogadjaj,
            set_lista=[
                {'redni_broj': 1, 'naziv': 'Kolo iz Slavonije'},
                {'redni_broj': 2, 'naziv': 'Šokačko kolo'},
            ],
            proba_prije_nastupa=True,
            prijevoz='Autobus',
        )
        self.assertIsNotNone(plan.pk)
        self.assertEqual(len(plan.set_lista), 2)

    # ═══════════════════════════════════════════════════════════════
    # RIBARI — ŠPORTSKI RIBOLOV
    # ═══════════════════════════════════════════════════════════════

    def test_11_ribari_create_revir(self):
        """Kreiranje ribolovnog revira."""
        from udruge.models import Revir
        revir = Revir.objects.create(
            company=self.company,
            naziv='Jezero Borovik',
            tip='jezero',
            lokacija='Našice',
            povrsina_ha=Decimal('45.00'),
            glavne_vrste=['šaran', 'som', 'štuka'],
            max_dnevni_ulov_kg=Decimal('5.00'),
        )
        self.assertIsNotNone(revir.pk)
        self.assertEqual(len(revir.glavne_vrste), 3)
        self.assertFalse(revir.zabrana_ribolova)

    def test_12_ribari_create_dozvola(self):
        """Kreiranje ribolovne dozvole."""
        from udruge.models import RibolovnaDozvola, Revir
        clan = self._clan()
        revir = Revir.objects.create(
            company=self.company, naziv='Rijeka Drava', tip='rijeka',
        )
        dozvola = RibolovnaDozvola.objects.create(
            company=self.company,
            clan=clan,
            kategorija='A',
            broj_dozvole='RD-2026-001',
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=365),
            cijena=Decimal('30.00'),
            placena=True,
        )
        dozvola.reviri.add(revir)
        self.assertIsNotNone(dozvola.pk)
        self.assertTrue(dozvola.is_valid)

    def test_13_ribari_create_ulov(self):
        """Kreiranje evidencije ulova."""
        from udruge.models import UlovEvidencija, Revir
        clan = self._clan()
        revir = Revir.objects.create(
            company=self.company, naziv='Jezero Kopačevo', tip='jezero',
        )
        ulov = UlovEvidencija.objects.create(
            company=self.company,
            clan=clan,
            revir=revir,
            datum=date.today(),
            vrsta_ribe='Šaran',
            tezina_kg=Decimal('3.50'),
            duzina_cm=52,
            metoda='stap',
        )
        self.assertIsNotNone(ulov.pk)
        self.assertIn('Šaran', str(ulov))

    def test_14_ribari_create_poribljavanje(self):
        """Kreiranje zapisa poribljavanja."""
        from udruge.models import Poribljavanje, Revir
        revir = Revir.objects.create(
            company=self.company, naziv='Bara Šarkanj', tip='bare',
        )
        porib = Poribljavanje.objects.create(
            company=self.company,
            revir=revir,
            datum=date.today(),
            vrsta_ribe='Šaran',
            kolicina_kg=Decimal('500.00'),
            komada=200,
            dobavljac='Ribnjak Našice',
            cijena_eur=Decimal('1500.00'),
            financirano_iz='članarine',
        )
        self.assertIsNotNone(porib.pk)
        self.assertEqual(porib.komada, 200)

    def test_15_ribari_cuvarska_straza(self):
        """Kreiranje čuvarske straže."""
        from udruge.models import CuvarskaStraza, Revir
        cuvar = self._clan()
        revir = Revir.objects.create(
            company=self.company, naziv='Rijeka Vuka', tip='rijeka',
        )
        straza = CuvarskaStraza.objects.create(
            company=self.company,
            cuvar=cuvar,
            revir=revir,
            datum_od=timezone.now(),
            datum_do=timezone.now() + timedelta(hours=8),
            prekrsaji=0,
            zapisnik='Bez primjedbi.',
        )
        self.assertIsNotNone(straza.pk)
        self.assertEqual(straza.prekrsaji, 0)

    def test_16_ribari_dozvola_validity(self):
        """Provjera is_valid property na dozvoli."""
        from udruge.models import RibolovnaDozvola
        clan = self._clan()
        # Valjana dozvola
        d1 = RibolovnaDozvola.objects.create(
            company=self.company, clan=clan, kategorija='A',
            broj_dozvole='RD-VAL-001',
            valid_from=date.today() - timedelta(days=10),
            valid_until=date.today() + timedelta(days=355),
            placena=True,
        )
        self.assertTrue(d1.is_valid)

        # Istekla dozvola
        d2 = RibolovnaDozvola.objects.create(
            company=self.company, clan=clan, kategorija='C',
            broj_dozvole='RD-EXP-001',
            valid_from=date.today() - timedelta(days=400),
            valid_until=date.today() - timedelta(days=35),
            placena=True,
        )
        self.assertFalse(d2.is_valid)

        # Neplaćena dozvola
        d3 = RibolovnaDozvola.objects.create(
            company=self.company, clan=clan, kategorija='B',
            broj_dozvole='RD-UNP-001',
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=7),
            placena=False,
        )
        self.assertFalse(d3.is_valid)

    # ═══════════════════════════════════════════════════════════════
    # PČELARI — PČELARSKA DRUŠTVA
    # ═══════════════════════════════════════════════════════════════

    def test_17_pcelari_create_pcelinjak(self):
        """Kreiranje pčelinjaka."""
        from udruge.models import Pcelinjak
        clan = self._clan()
        pcelinjak = Pcelinjak.objects.create(
            company=self.company,
            vlasnik=clan,
            naziv='Pčelinjak Lipovac',
            lokacija='Lipovac, Čepin',
            jrdz_broj='JRDZ-123',
            stacionarni=True,
        )
        self.assertIsNotNone(pcelinjak.pk)
        self.assertEqual(pcelinjak.broj_kosnica, 0)

    def test_18_pcelari_create_kosnica(self):
        """Kreiranje košnice u pčelinjaku."""
        from udruge.models import Pcelinjak, Kosnica
        clan = self._clan()
        pcelinjak = Pcelinjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Pčelinjak A', lokacija='Čepin',
        )
        kosnica = Kosnica.objects.create(
            pcelinjak=pcelinjak,
            oznaka='K-01',
            tip='lr',
            status='aktivna',
            godina_matice=2025,
            boja_matice='žuta',
            snaga_zajednice=4,
        )
        self.assertIsNotNone(kosnica.pk)
        self.assertEqual(pcelinjak.broj_kosnica, 1)

    def test_19_pcelari_create_tretman(self):
        """Kreiranje tretmana košnice (varroa)."""
        from udruge.models import Pcelinjak, Kosnica, TretmanKosnice
        clan = self._clan()
        pcelinjak = Pcelinjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Pčelinjak B', lokacija='Đakovo',
        )
        kosnica = Kosnica.objects.create(
            pcelinjak=pcelinjak, oznaka='K-02', tip='db', status='aktivna',
        )
        tretman = TretmanKosnice.objects.create(
            kosnica=kosnica,
            datum=date.today(),
            tip='varroa',
            lijek='Apivar',
            doza='2 trake',
            karencija_do=date.today() + timedelta(days=42),
        )
        self.assertIsNotNone(tretman.pk)
        self.assertEqual(tretman.tip, 'varroa')

    def test_20_pcelari_create_med(self):
        """Kreiranje zapisa proizvodnje meda."""
        from udruge.models import Pcelinjak, MedProizvodnja
        clan = self._clan()
        pcelinjak = Pcelinjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Pčelinjak C', lokacija='Našice',
        )
        med = MedProizvodnja.objects.create(
            pcelinjak=pcelinjak,
            datum_vrcanja=date.today(),
            vrsta='bagrem',
            kolicina_kg=Decimal('25.50'),
            vlaga_posto=Decimal('17.5'),
            broj_kosnica_vrcano=10,
            za_prodaju=True,
            cijena_eur_kg=Decimal('12.00'),
        )
        self.assertIsNotNone(med.pk)
        self.assertEqual(med.vrsta, 'bagrem')
        self.assertTrue(med.za_prodaju)

    def test_21_pcelari_create_selidba(self):
        """Kreiranje selidbe pčelinjaka."""
        from udruge.models import Pcelinjak, SelidbaLog
        clan = self._clan()
        pcelinjak = Pcelinjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Pčelinjak Mobil', lokacija='Čepin',
            stacionarni=False,
        )
        selidba = SelidbaLog.objects.create(
            pcelinjak=pcelinjak,
            datum=date.today(),
            odrediste='Sunčana dolina, Baranja',
            broj_kosnica=20,
            razlog='Bagremova paša',
        )
        self.assertIsNotNone(selidba.pk)
        self.assertEqual(selidba.broj_kosnica, 20)

    # ═══════════════════════════════════════════════════════════════
    # RAKIJA — PROIZVOĐAČI RAKIJE
    # ═══════════════════════════════════════════════════════════════

    def test_22_rakija_create_kotao(self):
        """Kreiranje destilacijskog kotla."""
        from udruge.models import DestilacijaKotao
        kotao = DestilacijaKotao.objects.create(
            company=self.company,
            registarski_broj='KT-2026-001',
            volumen_litara=100,
            tip='bakreni',
            lokacija='Čepin, Matije Gupca 5',
            
        )
        self.assertIsNotNone(kotao.pk)
        self.assertIn('KT-2026-001', str(kotao))

    def test_23_rakija_destilacija_auto_cistog(self):
        """Test auto-izračuna litara čistog alkohola pri save()."""
        from udruge.models import DestilacijaKotao, DestilacijaLog
        kotao = DestilacijaKotao.objects.create(
            company=self.company,
            registarski_broj='KT-AUTO-001',
            volumen_litara=80,
            
        )
        dest = DestilacijaLog.objects.create(
            kotao=kotao,
            datum=date.today(),
            sirovina='sljiva',
            kg_sirovina=Decimal('200.00'),
            litara_destilata=Decimal('20.00'),
            alkohol_posto=Decimal('45.0'),
        )
        # 20 * 45 / 100 = 9.0 litara čistog alkohola
        self.assertEqual(dest.litara_cistog_alkohola, Decimal('9.000'))

    def test_24_rakija_create_proizvod(self):
        """Kreiranje rakije kao gotovog proizvoda."""
        from udruge.models import RakijaProizvodnja
        rakija = RakijaProizvodnja.objects.create(
            company=self.company,
            naziv='Šljivovica domaća',
            tip_rakije='Šljivovica',
            litara=Decimal('15.00'),
            alkohol_posto=Decimal('42.0'),
            godina=2025,
            za_prodaju=False,
        )
        self.assertIsNotNone(rakija.pk)
        self.assertIn('Šljivovica', str(rakija))

    def test_25_rakija_trosarina_mali_proizvodac(self):
        """Test trošarinske prijave — mali proizvođač flag i auto izračun."""
        from udruge.models import TrosarinaPrijava
        # Mali proizvođač (<=50L č.a.)
        tp1 = TrosarinaPrijava.objects.create(
            company=self.company,
            godina=2025,
            ukupno_litara_destilata=Decimal('100.00'),
            prosjecni_alkohol_posto=Decimal('42.0'),
            ukupno_litara_cistog=Decimal('42.00'),
            stopa_eur_hl=Decimal('0.00'),
        )
        self.assertTrue(tp1.mali_proizvodac)
        self.assertEqual(tp1.iznos_trosarine, Decimal('0.00'))

    def test_26_rakija_trosarina_veliki_proizvodac(self):
        """Test trošarine za velikog proizvođača (>50L č.a.)."""
        from udruge.models import TrosarinaPrijava
        tp2 = TrosarinaPrijava.objects.create(
            company=self.company,
            godina=2024,
            ukupno_litara_destilata=Decimal('500.00'),
            prosjecni_alkohol_posto=Decimal('42.0'),
            ukupno_litara_cistog=Decimal('210.00'),
            stopa_eur_hl=Decimal('1047.27'),
        )
        self.assertFalse(tp2.mali_proizvodac)
        # 210 / 100 * 1047.27 = 2199.267
        expected = Decimal('210.00') / 100 * Decimal('1047.27')
        self.assertEqual(tp2.iznos_trosarine, expected)

    # ═══════════════════════════════════════════════════════════════
    # VOĆARI — VOĆARSKA UDRUŽENJA
    # ═══════════════════════════════════════════════════════════════

    def test_27_vocari_create_vocnjak(self):
        """Kreiranje voćnjaka."""
        from udruge.models import Vocnjak
        clan = self._clan()
        vocnjak = Vocnjak.objects.create(
            company=self.company,
            vlasnik=clan,
            naziv='Jabučnjak Čepin',
            vrsta='jabuka',
            sorta='Idared',
            podloga='M9',
            sustav_uzgoja='spalir',
            broj_stabala=500,
            godina_sadnje=2020,
            povrsina_ha=Decimal('1.50'),
        )
        self.assertIsNotNone(vocnjak.pk)
        self.assertEqual(vocnjak.starost_godina, timezone.now().year - 2020)

    def test_28_vocari_create_berba(self):
        """Kreiranje evidencije berbe."""
        from udruge.models import Vocnjak, BerbaLog
        clan = self._clan()
        vocnjak = Vocnjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Šljivik', vrsta='sljiva', sorta='Požegača',
            broj_stabala=100, godina_sadnje=2018,
        )
        berba = BerbaLog.objects.create(
            vocnjak=vocnjak,
            datum=date.today(),
            kolicina_kg=Decimal('1200.00'),
            kvaliteta='I',
            broj_radnika=4,
            sati_berbe=Decimal('8.0'),
            za_prodaju=True,
            za_preradu=True,
            cijena_eur_kg=Decimal('0.80'),
        )
        self.assertIsNotNone(berba.pk)
        self.assertTrue(berba.za_preradu)

    def test_29_vocari_tretman_karencija_auto(self):
        """Test auto-izračuna karencija_do kod tretmana voćnjaka."""
        from udruge.models import Vocnjak, TretmanVocnjaka
        clan = self._clan()
        vocnjak = Vocnjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Voćnjak Trešnja', vrsta='tresnja', sorta='Burlat',
            broj_stabala=50,
        )
        tretman = TretmanVocnjaka.objects.create(
            vocnjak=vocnjak,
            datum=date.today(),
            tip='fungicid',
            sredstvo='Neoram WG',
            doza='2.5 kg/ha',
            karencija_dana=21,
            tretirao='Ivan Horvat',
        )
        # Auto karencija_do = datum + 21 dana
        self.assertEqual(tretman.karencija_do, date.today() + timedelta(days=21))

    def test_30_vocari_vocnjak_starost(self):
        """Provjera starost_godina property."""
        from udruge.models import Vocnjak
        vocnjak = Vocnjak.objects.create(
            company=self.company,
            naziv='Stari orah',
            vrsta='orah',
            broj_stabala=10,
            godina_sadnje=2010,
        )
        self.assertEqual(vocnjak.starost_godina, timezone.now().year - 2010)

        # Voćnjak bez godine sadnje
        vocnjak2 = Vocnjak.objects.create(
            company=self.company,
            naziv='Novi nasad',
            vrsta='malina',
            broj_stabala=200,
        )
        self.assertIsNone(vocnjak2.starost_godina)

    # ═══════════════════════════════════════════════════════════════
    # CELERY TASK TESTOVI
    # ═══════════════════════════════════════════════════════════════

    def test_31_task_check_ribolovne_dozvole(self):
        """Test dnevnog taska za provjeru ribolovnih dozvola."""
        from udruge.models import RibolovnaDozvola
        clan = self._clan(whatsapp_opt_in=True, phone='0912345678')
        RibolovnaDozvola.objects.create(
            company=self.company, clan=clan, kategorija='A',
            broj_dozvole='RD-TASK-001',
            valid_from=date.today() - timedelta(days=350),
            valid_until=date.today() + timedelta(days=10),
            placena=True,
        )
        with patch('core.whatsapp.send_text', return_value={'ok': True}):
            from udruge.tasks import check_ribolovne_dozvole
            result = check_ribolovne_dozvole()
        self.assertGreaterEqual(result['expiring_14d'], 1)

    def test_32_task_check_tretman_kosnica(self):
        """Test taska za provjeru tretmana košnica."""
        from udruge.models import Pcelinjak, Kosnica
        clan = self._clan()
        pcelinjak = Pcelinjak.objects.create(
            company=self.company, vlasnik=clan,
            naziv='Pčelinjak Task', lokacija='Test',
        )
        Kosnica.objects.create(
            pcelinjak=pcelinjak, oznaka='KT-01',
            tip='lr', status='aktivna',
        )
        from udruge.tasks import check_tretman_kosnica_reminders
        result = check_tretman_kosnica_reminders()
        # Zavisi o sezoni — ali task se mora izvršiti bez greške
        self.assertIsInstance(result, dict)

    def test_33_task_generate_trosarina(self):
        """Test generiranja trošarinskog izvještaja."""
        from udruge.models import DestilacijaKotao, DestilacijaLog
        kotao = DestilacijaKotao.objects.create(
            company=self.company,
            registarski_broj='KT-TASK-001',
            volumen_litara=100,
            
        )
        DestilacijaLog.objects.create(
            kotao=kotao, datum=date.today(),
            sirovina='sljiva', kg_sirovina=Decimal('150.00'),
            litara_destilata=Decimal('15.00'), alkohol_posto=Decimal('45.0'),
        )
        DestilacijaLog.objects.create(
            kotao=kotao, datum=date.today() - timedelta(days=30),
            sirovina='grozdje', kg_sirovina=Decimal('200.00'),
            litara_destilata=Decimal('18.00'), alkohol_posto=Decimal('40.0'),
        )
        from udruge.tasks import generate_trosarina_report
        result = generate_trosarina_report(self.company.pk, timezone.now().year)
        self.assertEqual(result['destilacija_count'], 2)
        self.assertTrue(result['mali_proizvodac'])
        # 15*45/100 + 18*40/100 = 6.75 + 7.2 = 13.95
        self.assertAlmostEqual(result['ukupno_cistog_alkohola'], 13.95, places=1)
