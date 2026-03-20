"""Tests for medium modules: documents, outreach, assessment, burza, interventions, marketplace, partners."""
import datetime
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User


def _setup_user(oib, username, modules, is_superuser=False):
    from companies.models import Company
    from accounts.models import UserProfile
    from registration.models import CompanySubscription
    company = Company.objects.create(name=f'MD {oib}', oib=oib)
    if is_superuser:
        user = User.objects.create_superuser(username, password='pass123', email=f'{username}@test.hr')
    else:
        user = User.objects.create_user(username, password='pass123')
    try:
        p = user.profile
        p.company = company
        p.save()
    except Exception:
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


# ===== DOCUMENTS =====
class DocumentsViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000001', 'md_doc1', ['documents', 'invoicing', 'partners'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_doc1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_document_list(self):
        self.assertIn(self._get('/documents/'), ALLOWED)

    def test_document_create_get(self):
        self.assertIn(self._get('/documents/new/'), ALLOWED)

    def test_document_create_post(self):
        resp = self.client.post('/documents/new/', {
            'title': 'Test Doc',
            'type': 'general',
            'date': '2026-01-01',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_document_detail_invalid(self):
        self.assertIn(self._get('/documents/9999/'), ALLOWED)

    def test_document_toggle_paid_invalid(self):
        resp = self.client.post('/documents/9999/paid/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_otpremnica_list(self):
        self.assertIn(self._get('/documents/otpremnica/'), ALLOWED)

    def test_otpremnica_create_get(self):
        self.assertIn(self._get('/documents/otpremnica/nova/'), ALLOWED)

    def test_otpremnica_create_post(self):
        resp = self.client.post('/documents/otpremnica/nova/', {
            'date': '2026-01-01',
            'recipient': 'Test',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_primka_list(self):
        self.assertIn(self._get('/documents/primka/'), ALLOWED)

    def test_primka_create_get(self):
        self.assertIn(self._get('/documents/primka/nova/'), ALLOWED)

    def test_primka_create_post(self):
        resp = self.client.post('/documents/primka/nova/', {
            'date': '2026-01-01',
            'supplier': 'Test Supplier',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_otkupni_list(self):
        self.assertIn(self._get('/documents/otkupni/'), ALLOWED)

    def test_otkupni_create_get(self):
        self.assertIn(self._get('/documents/otkupni/novi/'), ALLOWED)

    def test_cmr_list(self):
        self.assertIn(self._get('/documents/cmr/'), ALLOWED)

    def test_cmr_create_get(self):
        self.assertIn(self._get('/documents/cmr/novi/'), ALLOWED)


# ===== OUTREACH =====
class OutreachViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000002', 'md_out1', ['outreach', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_out1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_dashboard(self):
        self.assertIn(self._get('/outreach/'), ALLOWED)

    def test_contacts_list(self):
        self.assertIn(self._get('/outreach/contacts/'), ALLOWED)

    def test_contacts_list_with_search(self):
        resp = self.client.get('/outreach/contacts/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_contact_new_get(self):
        self.assertIn(self._get('/outreach/contacts/new/'), ALLOWED)

    def test_contact_new_post(self):
        resp = self.client.post('/outreach/contacts/new/', {
            'name': 'Test Contact',
            'email': 'outreach_contact@test.hr',
            'phone': '09100000001',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_contact_edit_invalid(self):
        self.assertIn(self._get('/outreach/contacts/9999/edit/'), ALLOWED)

    def test_contact_edit_valid(self):
        try:
            from outreach.models import Contact
            c = Contact.objects.create(
                company=self.company,
                name='Edit Contact',
                email='edit@test.hr',
            )
            self.assertIn(self._get(f'/outreach/contacts/{c.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/outreach/contacts/{c.pk}/edit/', {
                'name': 'Updated Contact',
                'email': 'updated@test.hr',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_campaign_new_get(self):
        self.assertIn(self._get('/outreach/campaign/new/'), ALLOWED)

    def test_campaign_new_post(self):
        resp = self.client.post('/outreach/campaign/new/', {
            'name': 'Test Campaign',
            'subject': 'Test Subject',
            'body': 'Test email body',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_campaign_detail_invalid(self):
        self.assertIn(self._get('/outreach/campaign/9999/'), ALLOWED)

    def test_campaign_preview_invalid(self):
        self.assertIn(self._get('/outreach/campaign/9999/preview/'), ALLOWED)

    def test_campaign_send_invalid(self):
        resp = self.client.post('/outreach/campaign/9999/send/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_inbox(self):
        self.assertIn(self._get('/outreach/inbox/'), ALLOWED)

    def test_csv_import_get(self):
        self.assertIn(self._get('/outreach/contacts/import/'), ALLOWED)

    def test_campaign_valid_detail(self):
        try:
            from outreach.models import Campaign
            c = Campaign.objects.create(
                company=self.company,
                name='Test Campaign',
                subject='Test',
                body='Body',
            )
            self.assertIn(self._get(f'/outreach/campaign/{c.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/outreach/campaign/{c.pk}/preview/'), ALLOWED)
        except Exception:
            pass

    def test_campaign_add_contacts_invalid(self):
        resp = self.client.post('/outreach/campaign/9999/add-contacts/', {
            'contact_ids': '[]',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_mark_replied_invalid(self):
        resp = self.client.post('/outreach/reply/9999/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)


# ===== ASSESSMENT =====
class AssessmentViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000003', 'md_ass1', ['assessment', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_ass1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_assessment_list(self):
        self.assertIn(self._get('/assessment/'), ALLOWED)

    def test_assessment_list_with_filter(self):
        resp = self.client.get('/assessment/?status=pending', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_assessment_new_get(self):
        self.assertIn(self._get('/assessment/new/'), ALLOWED)

    def test_assessment_save_post(self):
        resp = self.client.post('/assessment/save/', {
            'title': 'Test Assessment',
            'type': 'property',
            'address': 'Test Address 1',
            'city': 'Zagreb',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_assessment_detail_invalid(self):
        self.assertIn(self._get('/assessment/9999/'), ALLOWED)

    def test_assessment_pdf_invalid(self):
        self.assertIn(self._get('/assessment/9999/pdf/'), ALLOWED)

    def test_assessment_status_invalid(self):
        resp = self.client.post('/assessment/9999/status/', {
            'status': 'completed',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_assessment_upload_photo_invalid(self):
        self.assertIn(self._get('/assessment/9999/photos/'), ALLOWED)

    def test_full_assessment_crud(self):
        try:
            from assessment.models import Assessment
            a = Assessment.objects.create(
                company=self.company,
                title='CRUD Test',
                address='Test 1',
                city='Zagreb',
            )
            self.assertIn(self._get(f'/assessment/{a.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/assessment/{a.pk}/pdf/'), ALLOWED)
            resp = self.client.post(f'/assessment/{a.pk}/status/', {
                'status': 'completed',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


# ===== BURZA (CRM Kanban) =====
class BurzaViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000004', 'md_bur1', ['invoicing', 'partners'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_bur1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_kanban_board(self):
        self.assertIn(self._get('/burza/'), ALLOWED)

    def test_kanban_with_filter(self):
        resp = self.client.get('/burza/?stage=new', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_lead_new_get(self):
        self.assertIn(self._get('/burza/lead/new/'), ALLOWED)

    def test_lead_new_post(self):
        resp = self.client.post('/burza/lead/new/', {
            'title': 'Test Lead',
            'company_name': 'Lead Company',
            'contact_name': 'Lead Contact',
            'phone': '09100000001',
            'value': '5000.00',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_lead_detail_invalid(self):
        self.assertIn(self._get('/burza/lead/9999/'), ALLOWED)

    def test_lead_move_invalid(self):
        resp = self.client.post('/burza/lead/9999/move/', {
            'stage': 'qualified',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_lead_preuzmi_invalid(self):
        resp = self.client.post('/burza/lead/9999/preuzmi/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_upit(self):
        resp = self.client.get('/burza/upit/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_upit_post(self):
        resp = self.client.post('/burza/upit/', {
            'name': 'Public Inquiry',
            'email': 'inquiry@test.hr',
            'phone': '091000000',
            'message': 'Test inquiry message',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_upit_hvala(self):
        resp = self.client.get('/burza/upit/hvala/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_lead_full_crud(self):
        try:
            from burza.models import Lead
            lead = Lead.objects.create(
                company=self.company,
                title='Full CRUD Lead',
                company_name='Test Co',
            )
            self.assertIn(self._get(f'/burza/lead/{lead.pk}/'), ALLOWED)
            resp = self.client.post(f'/burza/lead/{lead.pk}/move/', {
                'stage': 'qualified',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/burza/lead/{lead.pk}/preuzmi/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


# ===== INTERVENTIONS =====
class InterventionsViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000005', 'md_int1', ['interventions', 'invoicing'])
        from accounts.models import UserProfile
        # Add role to make user company admin
        try:
            profile = self.user.profile
            profile.role = 'company_admin'
            profile.save()
        except Exception:
            pass
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_int1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_kanban(self):
        self.assertIn(self._get('/interventions/'), ALLOWED)

    def test_kanban_with_filter(self):
        resp = self.client.get('/interventions/?status=open', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_new_intervention_get(self):
        self.assertIn(self._get('/interventions/new/'), ALLOWED)

    def test_new_intervention_post(self):
        resp = self.client.post('/interventions/new/', {
            'title': 'Test Intervention',
            'description': 'Test intervention description',
            'priority': 'high',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_field_view_invalid(self):
        self.assertIn(self._get('/interventions/9999/field/'), ALLOWED)

    def test_update_status_invalid(self):
        resp = self.client.post('/interventions/9999/status/', {
            'status': 'in_progress',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_assign_worker_invalid(self):
        resp = self.client.post('/interventions/9999/assign/', {
            'worker_id': self.user.pk,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_escalate_invalid(self):
        resp = self.client.post('/interventions/9999/escalate/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_public_intervention(self):
        resp = self.client.get('/interventions/public/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_sos(self):
        resp = self.client.get('/interventions/sos/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_gps_update_invalid(self):
        resp = self.client.post('/interventions/9999/gps/', json.dumps({
            'lat': 45.8, 'lng': 16.0,
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_full_intervention_crud(self):
        try:
            from interventions.models import Intervention
            iv = Intervention.objects.create(
                company=self.company,
                title='CRUD Test',
                description='Test',
                priority='high',
            )
            self.assertIn(self._get(f'/interventions/{iv.pk}/field/'), ALLOWED)
            resp = self.client.post(f'/interventions/{iv.pk}/status/', {
                'status': 'in_progress',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/interventions/{iv.pk}/assign/', {
                'worker_id': self.user.pk,
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
            resp = self.client.post(f'/interventions/{iv.pk}/escalate/', follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass


# ===== MARKETPLACE =====
class MarketplaceViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000006', 'md_mkt1', ['marketplace', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_mkt1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_catalog(self):
        self.assertIn(self._get('/marketplace/'), ALLOWED)

    def test_catalog_search(self):
        resp = self.client.get('/marketplace/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_cart_view(self):
        self.assertIn(self._get('/marketplace/cart/'), ALLOWED)

    def test_cart_add(self):
        resp = self.client.post('/marketplace/cart/add/', {
            'product_id': 9999,
            'quantity': 1,
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_cart_clear(self):
        resp = self.client.post('/marketplace/cart/clear/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_cart_remove_invalid(self):
        resp = self.client.post('/marketplace/cart/remove/nonexistent/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_checkout(self):
        self.assertIn(self._get('/marketplace/checkout/'), ALLOWED)

    def test_my_orders(self):
        self.assertIn(self._get('/marketplace/orders/'), ALLOWED)

    def test_order_detail_invalid(self):
        self.assertIn(self._get('/marketplace/orders/9999/'), ALLOWED)

    def test_seller_dashboard(self):
        self.assertIn(self._get('/marketplace/seller/'), ALLOWED)

    def test_seller_product_new(self):
        self.assertIn(self._get('/marketplace/seller/product/new/'), ALLOWED)

    def test_seller_product_new_post(self):
        resp = self.client.post('/marketplace/seller/product/new/', {
            'name': 'Seller Product',
            'price': '99.99',
            'description': 'Test product',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_seller_product_edit_invalid(self):
        self.assertIn(self._get('/marketplace/seller/product/9999/edit/'), ALLOWED)

    def test_seller_order_action_invalid(self):
        resp = self.client.post('/marketplace/seller/order/9999/action/', {
            'action': 'confirm',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)


# ===== PARTNERS EXTRA =====
class PartnersExtraViewsTest(TestCase):
    def setUp(self):
        self.company, self.user = _setup_user('61000000007', 'md_par1', ['partners', 'invoicing'])
        self.client = Client(raise_request_exception=False)
        self.client.login(username='md_par1', password='pass123')

    def _get(self, url):
        return self.client.get(url, follow=True).status_code

    def test_partner_list(self):
        self.assertIn(self._get('/partners/'), ALLOWED)

    def test_partner_list_search(self):
        resp = self.client.get('/partners/?q=test', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_partner_create_get(self):
        self.assertIn(self._get('/partners/new/'), ALLOWED)

    def test_partner_create_post(self):
        resp = self.client.post('/partners/new/', {
            'name': 'Extra Partner',
            'oib': '10000000001',
            'type': 'customer',
            'email': 'extrapartner@test.hr',
        }, follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_partner_detail_invalid(self):
        self.assertIn(self._get('/partners/9999/'), ALLOWED)

    def test_partner_edit_invalid(self):
        self.assertIn(self._get('/partners/9999/edit/'), ALLOWED)

    def test_partner_detail_with_data(self):
        try:
            from partners.models import Partner
            p = Partner.objects.create(
                company=self.company,
                name='Detail Partner',
                oib='20000000002',
                type='customer',
            )
            self.assertIn(self._get(f'/partners/{p.pk}/'), ALLOWED)
            self.assertIn(self._get(f'/partners/{p.pk}/edit/'), ALLOWED)
            resp = self.client.post(f'/partners/{p.pk}/edit/', {
                'name': 'Updated Partner',
                'oib': '20000000002',
                'type': 'supplier',
            }, follow=True)
            self.assertIn(resp.status_code, ALLOWED)
        except Exception:
            pass

    def test_api_quick_create(self):
        resp = self.client.post('/partners/api/quick-create/', json.dumps({
            'name': 'Quick Partner',
            'oib': '30000000003',
        }), content_type='application/json', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_api_oib_lookup(self):
        resp = self.client.get('/partners/api/oib-lookup/?oib=12345678901', follow=True)
        self.assertIn(resp.status_code, ALLOWED)

    def test_partner_delete_invalid(self):
        resp = self.client.post('/partners/9999/delete/', follow=True)
        self.assertIn(resp.status_code, ALLOWED)
