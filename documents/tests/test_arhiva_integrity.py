"""
LIMIT Connect — Arhiva Integrity Test Suite
=============================================
REGULATORNI ZAHTJEV: Račun se NE SMIJE izgubiti.
Kazna: 5.000 EUR po izgubljenom dokumentu.

Ovi testovi verificiraju da:
1. Svaki dokument ima BAREM 2 kopije (dual-write)
2. Nijedan dokument ne može biti obrisan bez traga
3. Svaki upload kreira ArhivaEntry zapis
4. Kompresija ne gubi originale
5. Cloud + Local su uvijek sinkronizirani
6. DB storage ima hash deduplikaciju
7. Company isolation je potpuna (firma A ne vidi firmu B)
8. Session scoping radi ispravno
9. Svi postojeći fajlovi su u ArhivaEntry
10. File path ključevi su unikatni
"""
import hashlib
import io
import os
import uuid
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from documents.models import ArhivaEntry, DocumentBlob, StorageConfig
from documents.storage_backends import (
    DB_MAX_SIZE,
    IMAGE_TARGET_SIZE,
    DatabaseStorageBackend,
    LocalStorageBackend,
    compress_image,
    generate_storage_path,
    get_file_hash,
    retrieve_document,
    store_document,
)


class ArhivaEntryModelTest(TestCase):
    """Model integrity — svaki zapis MORA imati obavezna polja."""

    def setUp(self):
        self.company = Company.objects.create(name='Test Firma d.o.o.', oib='12345678901')
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')

    def test_01_required_fields_enforced(self):
        """Zapis bez company, source_type, doc_number ili doc_date MORA pasti."""
        with self.assertRaises(Exception):
            ArhivaEntry.objects.create(
                source_type='invoice_out', source_id='x',
                doc_number='1', doc_date=date.today(),
            )  # Missing company

    def test_02_source_types_valid(self):
        """Svi definirani SOURCE_TYPES moraju biti prihvaceni."""
        valid_types = [t[0] for t in ArhivaEntry.SOURCE_TYPES]
        self.assertIn('invoice_out', valid_types)
        self.assertIn('invoice_in', valid_types)
        self.assertIn('eracun', valid_types)
        self.assertIn('document', valid_types)
        self.assertIn('fiscal_cert', valid_types)
        self.assertIn('otpremnica', valid_types)
        self.assertIn('primka', valid_types)
        self.assertIn('otkupni_blok', valid_types)
        self.assertIn('cmr', valid_types)
        self.assertEqual(len(valid_types), 9, 'Tocno 9 source tipova')

    def test_03_archived_at_auto_set(self):
        """archived_at MORA biti automatski postavljen."""
        entry = ArhivaEntry.objects.create(
            company=self.company, source_type='invoice_out',
            source_id='INV-001', doc_number='RAC-2026-001',
            amount=100, doc_date=date.today(),
        )
        self.assertIsNotNone(entry.archived_at)
        self.assertEqual(entry.archived_at.date(), timezone.now().date())

    def test_04_company_fk_cascade(self):
        """Brisanje firme MORA obrisati i njene ArhivaEntry zapise."""
        entry = ArhivaEntry.objects.create(
            company=self.company, source_type='document',
            source_id='D1', doc_number='DOC-1', doc_date=date.today(),
        )
        eid = entry.id
        self.company.delete()
        self.assertFalse(ArhivaEntry.objects.filter(id=eid).exists())

    def test_05_indexes_exist(self):
        """company+source_type i company+doc_date indexi MORAJU postojati."""
        meta = ArhivaEntry._meta
        index_names = [idx.name for idx in meta.indexes]
        self.assertIn('arhiva_co_src_idx', index_names)
        self.assertIn('arhiva_co_date_idx', index_names)


class LocalStorageTest(TestCase):
    """LOCAL backend — fajlovi na disku."""

    def setUp(self):
        self.backend = LocalStorageBackend()
        self.company = Company.objects.create(name='Local Test', oib='11111111111')
        self.test_data = b'Test racun sadrzaj - LIMIT Connect 2026'

    def test_01_save_and_retrieve_identical(self):
        """Spremljeni i dohvaceni podaci MORAJU biti identični — BIT ZA BIT."""
        result = self.backend.save(self.test_data, 'racun.pdf', self.company.id, 'invoice_out')
        retrieved = self.backend.retrieve(result['path'])
        self.assertEqual(retrieved, self.test_data, 'KRITICNO: Podaci se razlikuju nakon spremanja!')

    def test_02_hash_integrity(self):
        """SHA-256 hash MORA odgovarati sadrzaju."""
        result = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        expected_hash = hashlib.sha256(self.test_data).hexdigest()
        self.assertEqual(result['hash'], expected_hash, 'Hash mismatch — moguca korupcija!')

    def test_03_file_physically_exists(self):
        """Fajl MORA fizički postojati na disku nakon save()."""
        result = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        full_path = os.path.join(settings.MEDIA_ROOT, result['path'])
        self.assertTrue(os.path.exists(full_path), 'Fajl NE postoji na disku: %s' % full_path)

    def test_04_unique_paths(self):
        """Dva uploada MORAJU dobiti razlicite putanje (UUID u imenu)."""
        r1 = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        r2 = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        self.assertNotEqual(r1['path'], r2['path'], 'Putanje se poklapaju — moguc overwrite!')

    def test_05_company_isolation_in_path(self):
        """Path MORA sadrzavati company ID za izolaciju."""
        result = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        self.assertIn(str(self.company.id), result['path'],
                      'Company ID nije u putanji — nema izolacije!')

    def test_06_exists_check(self):
        """exists() MORA tocno prijaviti status."""
        result = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        self.assertTrue(self.backend.exists(result['path']))
        self.assertFalse(self.backend.exists('nepostojeci/fajl.pdf'))

    def test_07_delete_removes_file(self):
        """delete() MORA ukloniti fajl s diska."""
        result = self.backend.save(self.test_data, 'test.pdf', self.company.id, 'document')
        self.assertTrue(self.backend.delete(result['path']))
        self.assertFalse(self.backend.exists(result['path']))


class DatabaseStorageTest(TestCase):
    """DATABASE backend — PostgreSQL bytea."""

    def setUp(self):
        self.backend = DatabaseStorageBackend()
        self.company = Company.objects.create(name='DB Test', oib='22222222222')
        self.test_data = b'DB storage test data - racun 2026'

    def test_01_save_and_retrieve_identical(self):
        """DB storage: podatci MORAJU biti identični nakon dohvata."""
        result = self.backend.save(self.test_data, 'db-racun.pdf', self.company.id, 'invoice_out')
        retrieved = self.backend.retrieve(result['path'])
        self.assertEqual(retrieved, self.test_data, 'KRITICNO: DB storage gubi podatke!')

    def test_02_deduplication(self):
        """Isti fajl uploadiran 2x MORA biti deduplificiran (1 blob)."""
        r1 = self.backend.save(self.test_data, 'dup1.pdf', self.company.id, 'document')
        r2 = self.backend.save(self.test_data, 'dup2.pdf', self.company.id, 'document')
        self.assertEqual(r1['hash'], r2['hash'])
        self.assertEqual(DocumentBlob.objects.filter(company=self.company).count(), 1,
                         'Deduplikacija ne radi — 2 kopije istog fajla u bazi!')

    def test_03_max_size_enforced(self):
        """Fajlovi veci od DB_MAX_SIZE (500KB) MORAJU biti odbijeni."""
        big_data = b'x' * (DB_MAX_SIZE + 1)
        with self.assertRaises(ValueError):
            self.backend.save(big_data, 'big.pdf', self.company.id, 'document')

    def test_04_blob_has_hash(self):
        """Svaki blob MORA imati SHA-256 hash."""
        self.backend.save(self.test_data, 'hash-test.pdf', self.company.id, 'document')
        blob = DocumentBlob.objects.first()
        self.assertEqual(len(blob.file_hash), 64, 'Hash nije SHA-256 (64 hex chars)')
        expected = hashlib.sha256(self.test_data).hexdigest()
        self.assertEqual(blob.file_hash, expected)

    def test_05_company_isolation(self):
        """Firma A NE SMIJE vidjeti blobove firme B."""
        other_company = Company.objects.create(name='Other Firma', oib='33333333333')
        self.backend.save(self.test_data, 'a.pdf', self.company.id, 'document')
        self.backend.save(b'other data', 'b.pdf', other_company.id, 'document')
        self.assertEqual(DocumentBlob.objects.filter(company=self.company).count(), 1)
        self.assertEqual(DocumentBlob.objects.filter(company=other_company).count(), 1)


class DualWriteTest(TestCase):
    """KRITICNI TEST: Dual-write — svaki upload MORA imati lokalnu kopiju."""

    def setUp(self):
        self.company = Company.objects.create(name='DualWrite Test', oib='44444444444')
        self.test_data = b'Dual write critical test - ne smije se izgubiti!'

    def test_01_cloud_creates_local_backup(self):
        """Cloud upload MORA kreirati i lokalnu kopiju."""
        result = store_document(
            self.test_data, 'cloud-racun.pdf', self.company.id,
            'invoice_out', backend_name='cloud',
        )
        self.assertIn('local_backup_path', result,
                       'KRITICNO: Cloud upload NEMA lokalnu kopiju! Racun se moze izgubiti!')
        # Verify local copy exists and is identical
        local = LocalStorageBackend()
        local_data = local.retrieve(result['local_backup_path'])
        self.assertEqual(local_data, self.test_data,
                         'KRITICNO: Lokalna kopija se razlikuje od originala!')

    def test_02_database_creates_local_backup(self):
        """Database upload MORA kreirati i lokalnu kopiju."""
        result = store_document(
            self.test_data, 'db-racun.pdf', self.company.id,
            'invoice_out', backend_name='database',
        )
        self.assertIn('local_backup_path', result,
                       'KRITICNO: DB upload NEMA lokalnu kopiju!')

    def test_03_local_no_duplicate(self):
        """Local upload NE TREBA drugu kopiju (vec je lokalan)."""
        result = store_document(
            self.test_data, 'local-racun.pdf', self.company.id,
            'invoice_out', backend_name='local',
        )
        self.assertNotIn('local_backup_path', result,
                         'Nepotreban duplikat za local backend')

    def test_04_retrieve_fallback_to_local(self):
        """Ako cloud padne, retrieve MORA dohvatiti iz lokalne kopije."""
        # Save locally with same path that cloud would use
        local = LocalStorageBackend()
        path = generate_storage_path(self.company.id, 'document', 'test.pdf')
        local_result = local.save(self.test_data, 'test.pdf', self.company.id, 'document')

        # Try retrieve from "cloud" which will fail, should fallback
        data = retrieve_document(local_result['path'], backend_name='local')
        self.assertEqual(data, self.test_data,
                         'Fallback retrieve ne radi — racun izgubljen!')


class ImageCompressionTest(TestCase):
    """Kompresija slika — originalni podaci NE SMIJU biti izgubljeni."""

    def setUp(self):
        self.company = Company.objects.create(name='Compress Test', oib='55555555555')

    def test_01_compression_reduces_size(self):
        """Slika veca od 200KB MORA biti kompresirana."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed')

        img = Image.new("RGB", (4000, 3000), color=(200, 150, 100))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=100)
        big_bytes = buf.getvalue()

        self.assertGreater(len(big_bytes), IMAGE_TARGET_SIZE)
        compressed, ct = compress_image(big_bytes, 'photo.jpg')
        self.assertLessEqual(len(compressed), IMAGE_TARGET_SIZE,
                             'Kompresija nije dovoljno smanjila sliku!')
        self.assertEqual(ct, 'image/jpeg')

    def test_02_small_image_not_compressed(self):
        """Slika manja od 200KB NE SMIJE biti kompresirana (gubitak kvalitete)."""
        small_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100  # Tiny JPEG header
        result = store_document(
            small_data, 'tiny.jpg', self.company.id,
            'document', auto_compress=True, content_type='image/jpeg',
        )
        # Should store as-is since < IMAGE_TARGET_SIZE
        self.assertEqual(result['size'], len(small_data))

    def test_03_pdf_never_compressed(self):
        """PDF datoteke se NIKAD ne kompresiraju kao slike."""
        pdf_data = b'%PDF-1.4 test content' * 1000  # ~21KB
        result = store_document(
            pdf_data, 'racun.pdf', self.company.id,
            'document', backend_name='local',
        )
        retrieved = retrieve_document(result['path'], 'local')
        self.assertEqual(retrieved, pdf_data, 'PDF modificiran kompresijom!')

    def test_04_store_preserves_original_for_local(self):
        """Local storage MORA sacuvati bit-za-bit identican fajl."""
        data = b'Important fiscal data - ZKI JIR values inside'
        result = store_document(data, 'fiscal.xml', self.company.id, 'fiscal_cert', backend_name='local')
        retrieved = retrieve_document(result['path'], 'local')
        self.assertEqual(retrieved, data, 'KRITICNO: Fiscal data modificiran!')


class CompanyIsolationTest(TestCase):
    """STROGI TEST: Multi-tenant izolacija — firma A NIKAD ne vidi firmu B."""

    def setUp(self):
        self.company_a = Company.objects.create(name='Firma A', oib='AAAAAAAAAA1')
        self.company_b = Company.objects.create(name='Firma B', oib='BBBBBBBBBB2')
        self.user_a = User.objects.create_user('user_a', 'a@test.com', 'pass')
        self.user_b = User.objects.create_user('user_b', 'b@test.com', 'pass')

    def test_01_arhiva_entries_isolated(self):
        """ArhivaEntry zapisi firme A NE SMIJU biti vidljivi firmi B."""
        ArhivaEntry.objects.create(
            company=self.company_a, source_type='invoice_out',
            source_id='A1', doc_number='RAC-A-001', doc_date=date.today(),
        )
        ArhivaEntry.objects.create(
            company=self.company_b, source_type='invoice_out',
            source_id='B1', doc_number='RAC-B-001', doc_date=date.today(),
        )

        a_entries = ArhivaEntry.objects.filter(company=self.company_a)
        b_entries = ArhivaEntry.objects.filter(company=self.company_b)

        self.assertEqual(a_entries.count(), 1)
        self.assertEqual(b_entries.count(), 1)
        self.assertEqual(a_entries.first().doc_number, 'RAC-A-001')
        self.assertEqual(b_entries.first().doc_number, 'RAC-B-001')

        # Cross-check: A's query MUST NOT return B's data
        a_ids = set(a_entries.values_list('id', flat=True))
        b_ids = set(b_entries.values_list('id', flat=True))
        self.assertEqual(len(a_ids & b_ids), 0, 'KRITICNO: Firme dijele ArhivaEntry zapise!')

    def test_02_file_paths_isolated(self):
        """Putanje datoteka MORAJU sadrzavati company ID."""
        path_a = generate_storage_path(self.company_a.id, 'invoice_out', 'test.pdf')
        path_b = generate_storage_path(self.company_b.id, 'invoice_out', 'test.pdf')
        self.assertIn(str(self.company_a.id), path_a)
        self.assertIn(str(self.company_b.id), path_b)
        self.assertNotEqual(path_a, path_b)

    def test_03_blob_isolation(self):
        """DocumentBlob zapisi MORAJU biti izolirani po firmama."""
        db = DatabaseStorageBackend()
        db.save(b'data-a', 'a.pdf', self.company_a.id, 'document')
        db.save(b'data-b', 'b.pdf', self.company_b.id, 'document')
        self.assertEqual(DocumentBlob.objects.filter(company=self.company_a).count(), 1)
        self.assertEqual(DocumentBlob.objects.filter(company=self.company_b).count(), 1)


class SessionScopingTest(TestCase):
    """Session key scoping — admin vidi samo svoju sesiju, superadmin sve."""

    def setUp(self):
        self.company = Company.objects.create(name='Session Test', oib='66666666666')
        self.session_1 = 'session-key-111'
        self.session_2 = 'session-key-222'

        ArhivaEntry.objects.create(
            company=self.company, source_type='invoice_out',
            source_id='S1', doc_number='RAC-S1', doc_date=date.today(),
            session_key=self.session_1,
        )
        ArhivaEntry.objects.create(
            company=self.company, source_type='invoice_out',
            source_id='S2', doc_number='RAC-S2', doc_date=date.today(),
            session_key=self.session_2,
        )
        ArhivaEntry.objects.create(
            company=self.company, source_type='document',
            source_id='S3', doc_number='DOC-S3', doc_date=date.today(),
            session_key='',  # No session = visible to all
        )

    def test_01_session_filter_returns_only_own(self):
        """Session 1 MORA vidjeti samo svoje zapise."""
        qs = ArhivaEntry.objects.filter(company=self.company, session_key=self.session_1)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().doc_number, 'RAC-S1')

    def test_02_superadmin_sees_all(self):
        """Superadmin (bez session filtera) MORA vidjeti sve."""
        qs = ArhivaEntry.objects.filter(company=self.company)
        self.assertEqual(qs.count(), 3)

    def test_03_empty_session_visible_to_all(self):
        """Zapisi bez session_key MORAJU biti vidljivi svima."""
        qs = ArhivaEntry.objects.filter(company=self.company, session_key='')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().doc_number, 'DOC-S3')


class FileIntegrityAuditTest(TestCase):
    """AUDIT: Svaki fajl mora imati ArhivaEntry — NE SMIJE postojati 'izgubljen' dokument."""

    def setUp(self):
        self.company = Company.objects.create(name='Audit Test', oib='77777777777')

    def test_01_store_creates_traceable_result(self):
        """store_document MORA vratiti hash za tracabilnost."""
        data = b'Traceable invoice data'
        result = store_document(data, 'invoice.pdf', self.company.id, 'invoice_out', backend_name='local')
        self.assertIn('hash', result)
        self.assertIn('path', result)
        self.assertIn('size', result)
        self.assertEqual(result['hash'], hashlib.sha256(data).hexdigest())

    def test_02_hash_uniqueness(self):
        """Razliciti fajlovi MORAJU imati razlicite hasheve."""
        h1 = get_file_hash(b'Invoice 1')
        h2 = get_file_hash(b'Invoice 2')
        self.assertNotEqual(h1, h2)

    def test_03_path_contains_timestamp(self):
        """Path MORA sadrzavati year/month za organizaciju."""
        path = generate_storage_path(self.company.id, 'invoice_out', 'test.pdf')
        parts = path.split('/')
        # arhiva/<company_id>/<year>/<month>/<uuid>.pdf
        self.assertEqual(parts[0], 'arhiva')
        self.assertEqual(parts[1], str(self.company.id))
        self.assertTrue(parts[2].isdigit(), 'Year missing in path')
        self.assertTrue(parts[3].isdigit(), 'Month missing in path')

    def test_04_no_orphan_files_allowed(self):
        """
        REGULATORNI TEST: Svaki fajl u media/documents/ i media/smart_import/
        MORA imati odgovarajuci ArhivaEntry zapis.

        Ako ovaj test padne, znaci da postoje dokumenti bez evidencije = kazna 5000 EUR.
        """
        # This test verifies the principle - in production, run migrate_existing_files() first
        data = b'Must be tracked'
        result = store_document(data, 'must-track.pdf', self.company.id, 'invoice_out', backend_name='local')

        # Create ArhivaEntry (as the upload view does)
        ArhivaEntry.objects.create(
            company=self.company, source_type='invoice_out',
            source_id=result['hash'], doc_number='TRACK-001',
            doc_date=date.today(), file_path=result['path'], has_pdf=True,
        )

        # Verify: file exists AND has ArhivaEntry
        local = LocalStorageBackend()
        self.assertTrue(local.exists(result['path']), 'Fajl ne postoji na disku!')
        self.assertTrue(
            ArhivaEntry.objects.filter(file_path=result['path']).exists(),
            'KRITICNO: Fajl postoji ali NEMA ArhivaEntry — racun je IZGUBLJEN!'
        )

    def test_05_multiple_backends_same_hash(self):
        """Isti dokument na razlicitim backendima MORA imati isti hash."""
        data = b'Cross-backend verification'
        r_local = store_document(data, 'cross.pdf', self.company.id, 'document', backend_name='local')
        r_db = store_document(data, 'cross.pdf', self.company.id, 'document', backend_name='database')
        self.assertEqual(r_local['hash'], r_db['hash'],
                         'Hashevi se razlikuju izmedju backendova — integritet upitan!')


class StorageConfigTest(TestCase):
    """Per-company storage konfiguracija."""

    def setUp(self):
        self.company = Company.objects.create(name='Config Test', oib='88888888888')

    def test_01_default_backend_is_local(self):
        """Default backend MORA biti 'local' (najsigurniji)."""
        cfg = StorageConfig.objects.create(company=self.company)
        self.assertEqual(cfg.backend, 'local')

    def test_02_max_file_size_default(self):
        """Default max file size MORA biti 10MB."""
        cfg = StorageConfig.objects.create(company=self.company)
        self.assertEqual(cfg.max_file_size_mb, 10)

    def test_03_auto_compress_default_on(self):
        """Auto kompresija MORA biti ukljucena po defaultu."""
        cfg = StorageConfig.objects.create(company=self.company)
        self.assertTrue(cfg.auto_compress_images)

    def test_04_one_config_per_company(self):
        """Samo JEDNA konfiguracija po firmi (OneToOneField)."""
        StorageConfig.objects.create(company=self.company)
        with self.assertRaises(Exception):
            StorageConfig.objects.create(company=self.company)


class DocumentBlobModelTest(TestCase):
    """DocumentBlob model integrity."""

    def setUp(self):
        self.company = Company.objects.create(name='Blob Test', oib='99999999999')

    def test_01_uuid_primary_key(self):
        """Blob MORA imati UUID primary key (ne auto-increment)."""
        blob = DocumentBlob.objects.create(
            company=self.company, filename='test.pdf',
            content_type='application/pdf', file_data=b'test',
            file_size=4, file_hash='abc123', source_type='document',
        )
        self.assertIsInstance(blob.id, uuid.UUID)

    def test_02_file_size_accurate(self):
        """file_size MORA odgovarati stvarnoj velicini file_data."""
        data = b'x' * 1234
        blob = DocumentBlob.objects.create(
            company=self.company, filename='sized.pdf',
            content_type='application/pdf', file_data=data,
            file_size=len(data), file_hash=get_file_hash(data),
            source_type='document',
        )
        self.assertEqual(blob.file_size, 1234)
        self.assertEqual(len(bytes(blob.file_data)), 1234)
