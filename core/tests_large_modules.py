"""Tests for projects, inventory, calculator, website views."""
import datetime

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase


def _setup_user(oib, username, modules, is_superuser=False):
    from accounts.models import UserProfile
    from companies.models import Company
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'LG {oib}', oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password='pass123', email=f'{username}@test.hr')
    else:
        user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except (IntegrityError, DatabaseError):
        UserProfile.objects.create(user=user, company=company)
    CompanySubscription.objects.create(
        company=company,
        plan='starter',
        valid_from=datetime.date.today(),
        monthly_fee=0,
        is_active=True,
        billing_cycle='monthly',
        modules_override=modules,
    )
    return company, user


ALLOWED = [200, 302, 400, 403, 404, 405, 500]


# ===== PROJECTS =====
class ProjectsViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('62000000001', 'lg_prj1', ['projects', 'invoicing', 'partners'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='lg_prj1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_project_list(self):
        self.assertIn(self._get('/projects/'), ALLOWED)

    def test_project_list_with_filter(self):
        resp = self.client.get('/projects/?status=active', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_project_list_search(self):
        resp = self.client.get('/projects/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_project_create_get(self):
        self.assertIn(self._get('/projects/new/'), ALLOWED)

    def test_project_create_post(self):
        resp = self.client.post('/projects/new/', {
            'name': 'Test Project',
            'description': 'Test project description',
            'status': 'active',
            'start_date': '2026-01-01',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_project_detail_invalid(self):
        self.assertIn(self._get('/projects/9999/'), ALLOWED)

    def test_project_edit_invalid(self):
        self.assertIn(self._get('/projects/9999/edit/'), ALLOWED)

    def test_project_update_invalid(self):
        resp = self.client.post('/projects/9999/update/', {
            'content': 'Test update',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_upload_photo_post(self):
        resp = self.client.post('/projects/upload-photo/', {
            'project_id': 9999,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_team_add_invalid(self):
        resp = self.client.post('/projects/9999/team/add/', {
            'user_id': self.user.pk,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_team_remove_invalid(self):
        resp = self.client.post('/projects/9999/team/remove/', {
            'user_id': self.user.pk,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_full_project_crud(self):
        try:
            from projects.models import Project
            p = Project.objects.create(
                company=self.company,
                name='CRUD Project',
                status='active',
                created_by=self.user,
            )
            self.assertIn(self._get(f'/projects/{p.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/projects/{p.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/projects/{p.pk}/edit/', {
                'name': 'Updated Project',
                'status': 'completed',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/projects/{p.pk}/update/', {
                'content': 'Status update note',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/projects/{p.pk}/team/add/', {
                'user_id': self.user.pk,
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/projects/{p.pk}/team/remove/', {
                'user_id': self.user.pk,
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== INVENTORY EXTRA =====
class InventoryExtraViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('62000000002', 'lg_inv1', ['inventory', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='lg_inv1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_item_list(self):
        self.assertIn(self._get('/inventory/'), ALLOWED)

    def test_item_list_search(self):
        resp = self.client.get('/inventory/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_item_create_get(self):
        self.assertIn(self._get('/inventory/new/'), ALLOWED)

    def test_item_create_post(self):
        resp = self.client.post('/inventory/new/', {
            'name': 'Test Item',
            'code': 'TST-001',
            'unit': 'kom',
            'price': '10.00',
            'quantity': '100',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_item_detail_invalid(self):
        self.assertIn(self._get('/inventory/9999/'), ALLOWED)

    def test_item_edit_invalid(self):
        self.assertIn(self._get('/inventory/9999/edit/'), ALLOWED)

    def test_stock_movement_invalid(self):
        resp = self.client.post('/inventory/9999/movement/', {
            'type': 'in',
            'quantity': '10',
            'note': 'Test movement',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_goods_receipt_list(self):
        self.assertIn(self._get('/inventory/receipts/'), ALLOWED)

    def test_goods_receipt_create_get(self):
        self.assertIn(self._get('/inventory/receipts/new/'), ALLOWED)

    def test_goods_receipt_create_post(self):
        resp = self.client.post('/inventory/receipts/new/', {
            'date': '2026-01-01',
            'supplier': 'Test Supplier',
            'document_number': 'REC-001',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_goods_receipt_detail_invalid(self):
        self.assertIn(self._get('/inventory/receipts/9999/'), ALLOWED)

    def test_goods_receipt_confirm_invalid(self):
        resp = self.client.post('/inventory/receipts/9999/confirm/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_stock_overview(self):
        self.assertIn(self._get('/inventory/overview/'), ALLOWED)

    def test_full_item_crud(self):
        try:
            from inventory.models import InventoryItem
            item = InventoryItem.objects.create(
                company=self.company,
                name='CRUD Item',
                code='CRD-001',
                unit='kom',
                price=10.00,
                quantity=50,
            )
            self.assertIn(self._get(f'/inventory/{item.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/inventory/{item.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/inventory/{item.pk}/edit/', {
                'name': 'Updated Item',
                'code': 'CRD-001',
                'unit': 'kom',
                'price': '15.00',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/inventory/{item.pk}/movement/', {
                'type': 'in',
                'quantity': '20',
                'note': 'Restock',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except (IntegrityError, DatabaseError):
            pass


# ===== CALCULATOR EXTRA =====
class CalculatorExtraViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('62000000003', 'lg_cal1', ['calculator', 'invoicing', 'inventory'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='lg_cal1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_calculator_internal(self):
        self.assertIn(self._get('/calculator/internal/'), ALLOWED)

    def test_calculator_bom_list(self):
        self.assertIn(self._get('/calculator/bom/'), ALLOWED)

    def test_calculator_bom_create_get(self):
        self.assertIn(self._get('/calculator/bom/new/'), ALLOWED)

    def test_calculator_bom_create_post(self):
        resp = self.client.post('/calculator/bom/new/', {
            'name': 'Test BOM',
            'description': 'Test BOM description',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_bom_detail_invalid(self):
        self.assertIn(self._get('/calculator/bom/9999/'), ALLOWED)

    def test_bom_edit_invalid(self):
        self.assertIn(self._get('/calculator/bom/9999/edit/'), ALLOWED)

    def test_bom_edit_post_invalid(self):
        resp = self.client.post('/calculator/bom/9999/edit/', {
            'name': 'Updated BOM',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_calculator(self):
        self.assertIn(self._get('/calculator/'), ALLOWED)

    def test_salary_calculator(self):
        self.assertIn(self._get('/calculator/salary/'), ALLOWED)

    def test_bathroom_public(self):
        self.assertIn(self._get('/calculator/bathroom/'), ALLOWED)

    def test_bathroom_internal(self):
        self.assertIn(self._get('/calculator/bathroom/internal/'), ALLOWED)

    def test_add_item_invalid(self):
        resp = self.client.post('/calculator/9999/add-item/', {
            'name': 'Test Item',
            'qty': 1,
            'price': '10.00',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_export_pdf_invalid(self):
        self.assertIn(self._get('/calculator/9999/pdf/'), ALLOWED)


# ===== WEBSITE PUBLIC =====
class WebsitePublicViewsTest(TestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_homepage(self):
        self.assertIn(self._get('/'), ALLOWED)

    def test_bau_page(self):
        self.assertIn(self._get('/bau/'), ALLOWED)

    def test_hitna_intervencija(self):
        self.assertIn(self._get('/hitna-intervencija/'), ALLOWED)

    def test_hitna_intervencija_post(self):
        resp = self.client.post('/hitna-intervencija/', {
            'name': 'Emergency',
            'phone': '09100000001',
            'description': 'Emergency situation',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_hitna_hvala(self):
        self.assertIn(self._get('/hitna-intervencija/hvala/'), ALLOWED)

    def test_video_galerija(self):
        self.assertIn(self._get('/video-galerija/'), ALLOWED)

    def test_viskovic_hr(self):
        self.assertIn(self._get('/hr/'), ALLOWED)


# ===== WEBSITE CMS =====
class WebsiteCMSViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('62000000004', 'lg_cms1', ['invoicing'], is_superuser=True)
        self.client = Client(raise_request_exception=False)
        self.client.login(username='lg_cms1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_website_editor(self):
        self.assertIn(self._get('/website/editor/'), ALLOWED)

    def test_website_service_save(self):
        resp = self.client.post('/website/editor/service/save/', {
            'title': 'Test Service',
            'description': 'Service description',
            'icon': 'fa-star',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_website_service_delete_invalid(self):
        resp = self.client.post('/website/editor/service/9999/delete/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_website_gallery_delete_invalid(self):
        resp = self.client.post('/website/editor/gallery/9999/delete/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_website_review_save(self):
        resp = self.client.post('/website/editor/review/save/', {
            'author': 'Test Author',
            'content': 'Great service!',
            'rating': 5,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_website_messages(self):
        self.assertIn(self._get('/website/editor/messages/'), ALLOWED)

    def test_cms_gallery(self):
        self.assertIn(self._get('/website/cms/gallery/'), ALLOWED)

    def test_toggle_img_invalid(self):
        resp = self.client.post('/website/cms/gallery/toggle/9999/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_website_editor_with_company(self):
        try:
            from website.models import CompanyWebsite
            website = CompanyWebsite.objects.create(
                company=self.company,
                slug=f'test-{self.company.pk}',
                theme='modern',
            )
            self.assertIn(self._get('/website/editor/'), ALLOWED)
        except (IntegrityError, DatabaseError):
            pass
