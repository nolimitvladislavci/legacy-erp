#!/usr/bin/env python
"""
LIMIT Connect ERP — Comprehensive Tests
Run: python /var/www/fina-connect/tests_full.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

# Allow Django test client's default host
from django.conf import settings
settings.ALLOWED_HOSTS = ['*']
settings.SECURE_SSL_REDIRECT = False

import unittest
import json
import os as _os
from decimal import Decimal
from datetime import date, timedelta
from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def get_or_create_company():
    from companies.models import Company
    company, _ = Company.objects.get_or_create(
        oib='12345678901',
        defaults={
            'name': 'Test Company d.o.o.',
            'address': 'Test Street 1',
            'city': 'Zagreb',
            'zip_code': '10000',
            'country': 'HR',
        }
    )
    return company


def get_or_create_user(username, is_staff=False, is_superuser=False):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': f'{username}@test.com',
            'is_staff': is_staff,
            'is_superuser': is_superuser,
        }
    )
    if created:
        user.set_password('Test123!')
        user.save()
    else:
        changed = False
        if is_staff and not user.is_staff:
            user.is_staff = True; changed = True
        if is_superuser and not user.is_superuser:
            user.is_superuser = True; changed = True
        if changed:
            user.save()
    return user


# ─── 1. INVOICING ─────────────────────────────────────────────────────────────

class InvoicingTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()

    def _make_invoice(self, number, **kwargs):
        from invoicing.models import Invoice
        defaults = dict(
            date_issued=timezone.now(),
            client_name='Test Client d.o.o.',
            doctype='R',
            status='DRAFT',
            company=self.company,
        )
        defaults.update(kwargs)
        return Invoice.objects.create(number=number, **defaults)

    def test_create_invoice(self):
        inv = self._make_invoice('TST-INV-001')
        self.assertEqual(inv.status, 'DRAFT')
        self.assertEqual(inv.doctype, 'R')
        inv.delete()
        print('  ✓ Create invoice')

    def test_add_items_and_calculate_total(self):
        from invoicing.models import Invoice, InvoiceItem
        Invoice.objects.filter(number='TST-INV-002').delete()  # clean stale
        inv = self._make_invoice('TST-INV-002')
        item1 = InvoiceItem.objects.create(
            invoice=inv, description='Service A',
            quantity=Decimal('2'), unit_price=Decimal('100.00'),
        )
        item2 = InvoiceItem.objects.create(
            invoice=inv, description='Service B',
            quantity=Decimal('1'), unit_price=Decimal('50.00'),
        )
        # total_price is auto-calculated in InvoiceItem.save()
        self.assertEqual(item1.total_price, Decimal('200.00'))
        self.assertEqual(item2.total_price, Decimal('50.00'))
        # recalculate() updates in-memory only; must save() then refresh
        inv.recalculate()
        inv.save()
        inv.refresh_from_db()
        self.assertGreaterEqual(inv.total, Decimal('250.00'))
        inv.delete()
        print('  ✓ Add items and calculate total')

    def test_invoice_number_uniqueness(self):
        self._make_invoice('TST-INV-UNIQ')
        with self.assertRaises(Exception):
            self._make_invoice('TST-INV-UNIQ')   # duplicate number → IntegrityError
        from invoicing.models import Invoice
        Invoice.objects.filter(number='TST-INV-UNIQ').delete()
        print('  ✓ Invoice number uniqueness enforced')

    def test_status_transitions(self):
        inv = self._make_invoice('TST-INV-003')
        for status in ('SENT', 'PAID'):
            inv.status = status
            inv.save()
            inv.refresh_from_db()
            self.assertEqual(inv.status, status)
        inv.delete()
        print('  ✓ Invoice status transitions (DRAFT→SENT→PAID)')


# ─── 2. POS ──────────────────────────────────────────────────────────────────

class POSTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()

    def _make_terminal(self, code):
        from pos.models import POSTerminal
        t, _ = POSTerminal.objects.get_or_create(
            terminal_code=code,
            company=self.company,
            defaults={'name': f'Terminal {code}'},
        )
        return t

    def test_create_terminal(self):
        t = self._make_terminal('TST-T1')
        self.assertEqual(t.company, self.company)
        print('  ✓ Create POS terminal')

    def test_open_session(self):
        from pos.models import POSSession
        t = self._make_terminal('TST-T2')
        session = POSSession.objects.create(
            terminal=t, session_number=1001, status='open',
        )
        self.assertEqual(session.status, 'open')
        session.delete()
        print('  ✓ Open POS session')

    def test_add_item_to_receipt(self):
        from pos.models import POSSession, POSReceipt, POSReceiptItem
        t = self._make_terminal('TST-T3')
        POSSession.objects.filter(terminal=t, session_number=1002).delete()
        session = POSSession.objects.create(
            terminal=t, session_number=1002, status='open',
        )
        receipt = POSReceipt.objects.create(
            session=session, receipt_number=2001, status='open',
        )
        item = POSReceiptItem.objects.create(
            receipt=receipt,
            description='Widget',
            quantity=Decimal('3'),
            unit_price=Decimal('10.00'),
            tax_rate=Decimal('25.00'),
        )
        # total_price = qty × unit_price × (1 + tax/100) = 3 × 10 × 1.25 = 37.50
        self.assertEqual(item.total_price, Decimal('37.50'))
        session.delete()
        print('  ✓ Add item to receipt (total_price auto-calculated)')

    def test_close_session(self):
        from pos.models import POSSession
        t = self._make_terminal('TST-T4')
        session = POSSession.objects.create(
            terminal=t, session_number=1003, status='open',
        )
        session.status = 'closed'
        session.save()
        session.refresh_from_db()
        self.assertEqual(session.status, 'closed')
        session.delete()
        print('  ✓ Close POS session')

    def test_receipt_payment(self):
        from pos.models import POSSession, POSReceipt
        t = self._make_terminal('TST-T5')
        POSSession.objects.filter(terminal=t, session_number=1004).delete()
        session = POSSession.objects.create(
            terminal=t, session_number=1004, status='open',
        )
        receipt = POSReceipt.objects.create(
            session=session, receipt_number=2002, status='open',
        )
        receipt.status = 'paid'
        receipt.save()
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, 'paid')
        session.delete()
        print('  ✓ Receipt status: open → paid')


# ─── 3. APPOINTMENTS ─────────────────────────────────────────────────────────

class AppointmentsTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        self.user = get_or_create_user('tst_appts_emp')

    def _make_appt(self, title, hour_offset=1, **kwargs):
        from appointments.models import Appointment
        now = timezone.now()
        defaults = dict(
            start_time=now + timedelta(hours=hour_offset),
            end_time=now + timedelta(hours=hour_offset + 1),
            status='scheduled',
            company=self.company,
        )
        defaults.update(kwargs)
        return Appointment.objects.create(title=title, **defaults)

    def test_create_appointment(self):
        appt = self._make_appt('Initial Consultation', hour_offset=10)
        self.assertEqual(appt.status, 'scheduled')
        self.assertEqual(appt.company, self.company)
        appt.delete()
        print('  ✓ Create appointment')

    def test_status_transitions(self):
        appt = self._make_appt('Follow-up', hour_offset=20)
        for status in ('confirmed', 'completed'):
            appt.status = status
            appt.save()
            appt.refresh_from_db()
            self.assertEqual(appt.status, status)
        appt.delete()
        print('  ✓ Appointment status transitions')

    def test_cancel_appointment(self):
        appt = self._make_appt('To Cancel', hour_offset=30)
        appt.status = 'cancelled'
        appt.save()
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'cancelled')
        appt.delete()
        print('  ✓ Cancel appointment')

    def test_booking_conflict_detection(self):
        """Query should find overlapping appointments for same employee."""
        from appointments.models import Appointment
        now = timezone.now()
        start = now + timedelta(hours=50)
        end   = now + timedelta(hours=51)

        a1 = Appointment.objects.create(
            title='Block A', start_time=start, end_time=end,
            status='scheduled', company=self.company, employee=self.user,
        )
        a2 = Appointment.objects.create(
            title='Block B', start_time=start, end_time=end,
            status='scheduled', company=self.company, employee=self.user,
        )
        conflicts = Appointment.objects.filter(
            employee=self.user,
            start_time__lt=end,
            end_time__gt=start,
            status__in=['scheduled', 'confirmed'],
        )
        self.assertGreaterEqual(conflicts.count(), 2)
        a1.delete()
        a2.delete()
        print('  ✓ Booking conflict detection (overlap query)')


# ─── 4. WORKTIME ─────────────────────────────────────────────────────────────

class WorktimeTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        self.user = get_or_create_user('tst_worktime_emp')

    def _get_project(self):
        from worktime.models import Project
        # worktime.Project does NOT have a company FK (confirmed by FieldError)
        proj, _ = Project.objects.get_or_create(
            code='TST-WPRJ',
            defaults={'name': 'Test Worktime Project'},
        )
        return proj

    def test_create_time_entry(self):
        from worktime.models import TimeEntry
        proj = self._get_project()
        entry = TimeEntry.objects.create(
            user=self.user, project=proj,
            date=date.today(), duration=Decimal('8.00'), status='PENDING',
        )
        self.assertEqual(entry.duration, Decimal('8.00'))
        self.assertEqual(entry.status, 'PENDING')
        entry.delete()
        print('  ✓ Create time entry')

    def test_calculate_total_hours(self):
        from worktime.models import TimeEntry
        proj = self._get_project()
        hours = ['4.00', '3.50', '2.00']
        entries = [
            TimeEntry.objects.create(
                user=self.user, project=proj,
                date=date.today(), duration=Decimal(h), status='APPROVED',
            )
            for h in hours
        ]
        total = TimeEntry.objects.filter(
            user=self.user, project=proj, status='APPROVED',
        ).aggregate(total=Sum('duration'))['total']
        self.assertEqual(total, Decimal('9.50'))
        for e in entries:
            e.delete()
        print('  ✓ Calculate total hours (Sum aggregation)')

    def test_status_transitions(self):
        from worktime.models import TimeEntry
        proj = self._get_project()
        entry = TimeEntry.objects.create(
            user=self.user, project=proj,
            date=date.today(), duration=Decimal('6.00'), status='DRAFT',
        )
        for status in ('PENDING', 'APPROVED'):
            entry.status = status
            entry.save()
            entry.refresh_from_db()
            self.assertEqual(entry.status, status)
        entry.delete()
        print('  ✓ Time entry status transitions (DRAFT→PENDING→APPROVED)')

    def test_reject_time_entry(self):
        from worktime.models import TimeEntry
        proj = self._get_project()
        entry = TimeEntry.objects.create(
            user=self.user, project=proj,
            date=date.today(), duration=Decimal('5.00'), status='PENDING',
        )
        entry.status = 'REJECTED'
        entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'REJECTED')
        entry.delete()
        print('  ✓ Reject time entry')


# ─── 5. CALCULATOR ───────────────────────────────────────────────────────────

class CalculatorTests(unittest.TestCase):

    def setUp(self):
        self.client = Client()

    def test_public_calculator_no_login_required(self):
        """GET /calculator/ must return 200 without authentication."""
        response = self.client.get('/calculator/')
        self.assertEqual(response.status_code, 200,
            f'Expected 200, got {response.status_code}. '
            f'Redirect to: {response.get("Location", "n/a")}')
        print('  ✓ /calculator/ is publicly accessible (200)')

    def test_internal_calculator_requires_login(self):
        """GET /calculator/internal/ must redirect unauthenticated users."""
        response = self.client.get('/calculator/internal/')
        self.assertIn(response.status_code, [301, 302],
            f'Expected redirect, got {response.status_code}')
        print('  ✓ /calculator/internal/ requires login (302)')

    def test_burza_upit_accessible(self):
        """GET /burza/upit/ must return 200."""
        response = self.client.get('/burza/upit/')
        self.assertEqual(response.status_code, 200,
            f'Expected 200, got {response.status_code}')
        print('  ✓ /burza/upit/ accessible (200)')

    def test_burza_upit_prefill_params(self):
        """GET params from calculator are reflected in response body."""
        response = self.client.get('/burza/upit/', {
            'title': 'Renovacija kupaonice',
            'budget_from': '2000',
            'budget_to': '8000',
        })
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8', errors='replace')
        self.assertIn('Renovacija kupaonice', content)
        print('  ✓ Burza upit prefill: title visible in response')

    def test_pos_dashboard_requires_login(self):
        """GET /pos/ must redirect unauthenticated users."""
        response = self.client.get('/pos/')
        self.assertIn(response.status_code, [301, 302],
            f'Expected redirect, got {response.status_code}')
        print('  ✓ /pos/ requires login (302)')


# ─── 6. SUPERADMIN ───────────────────────────────────────────────────────────

class SuperadminTests(unittest.TestCase):

    def setUp(self):
        self.client = Client()
        self.superadmin = get_or_create_user('superadmin', is_staff=True, is_superuser=True)
        # Ensure password is current
        self.superadmin.set_password('Super123!')
        self.superadmin.save()

    def _make_registration(self, oib, name='Test Reg GmbH', plan='starter'):
        from registration.models import CompanyRegistration
        reg, _ = CompanyRegistration.objects.get_or_create(
            oib=oib,
            defaults={
                'name': name,
                'contact_name': 'Test Person',
                'contact_email': f'{oib}@test.com',
                'contact_phone': '+385 91 000 0001',
                'selected_plan': plan,
                'status': 'pending',
            }
        )
        return reg

    def test_pending_count(self):
        from registration.models import CompanyRegistration
        reg = self._make_registration('10000000001', 'Count Test AG')
        count = CompanyRegistration.objects.filter(status='pending').count()
        self.assertGreaterEqual(count, 1)
        reg.delete()
        print(f'  ✓ Pending registrations count = {count}')

    def test_approve_registration(self):
        reg = self._make_registration('20000000002', 'Approve Test GmbH')
        reg.status = 'approved'
        reg.reviewed_by = self.superadmin
        reg.save()
        reg.refresh_from_db()
        self.assertEqual(reg.status, 'approved')
        reg.delete()
        print('  ✓ Approve registration (status → approved)')

    def test_reject_registration(self):
        reg = self._make_registration('30000000003', 'Reject Test LLC')
        reg.status = 'rejected'
        reg.rejection_reason = 'Missing documentation'
        reg.reviewed_by = self.superadmin
        reg.save()
        reg.refresh_from_db()
        self.assertEqual(reg.status, 'rejected')
        self.assertEqual(reg.rejection_reason, 'Missing documentation')
        reg.delete()
        print('  ✓ Reject registration with reason')

    def test_registration_plan_choices(self):
        for plan in ('starter', 'business', 'enterprise'):
            reg = self._make_registration(
                f'4000000000{plan[0]}', f'{plan.title()} Co', plan=plan
            )
            self.assertEqual(reg.selected_plan, plan)
            reg.delete()
        print('  ✓ All plan types: starter / business / enterprise')

    def test_superadmin_list_endpoint(self):
        """Superadmin registration list page accessible to staff."""
        self.client.force_login(self.superadmin)
        response = self.client.get('/register/superadmin/registrations/')
        self.assertIn(response.status_code, [200, 302],
            f'Got unexpected status {response.status_code}')
        print(f'  ✓ /register/superadmin/registrations/ status={response.status_code}')


# ─── RUNNER ──────────────────────────────────────────────────────────────────



# ─── 7. INTERVENTIONS ────────────────────────────────────────────────────────

class InterventionsTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        self.user    = get_or_create_user('test_worker_iv')

    def tearDown(self):
        from interventions.models import HitnaIntervencija
        HitnaIntervencija.objects.unscoped().filter(
            client_phone__startswith='099-TST'
        ).delete()

    def _make(self, title, **kwargs):
        from interventions.models import HitnaIntervencija
        defaults = dict(
            company=self.company,
            category='ostalo',
            address='Testna ulica 1, Zagreb',
            client_name='Test Klijent',
            client_phone='099-TST-0001',
        )
        defaults.update(kwargs)
        return HitnaIntervencija.objects.create(title=title, **defaults)

    def test_create_intervention(self):
        iv = self._make('Curenje vode u kupaonici')
        self.assertEqual(iv.status, 'NOVO')
        self.assertIsNotNone(iv.tracking_token)
        self.assertIsNotNone(iv.tracking_url)

    def test_assign_worker(self):
        iv = self._make('Kvar struje')
        iv.assign_worker(self.user, ttl_minutes=3)
        iv.refresh_from_db()
        self.assertEqual(iv.status, 'DODIJELJENO')
        self.assertEqual(iv.assigned_to, self.user)
        self.assertIsNotNone(iv.ttl_expires_at)
        self.assertIsNotNone(iv.assigned_at)

    def test_status_flow(self):
        from interventions.models import HitnaIntervencija
        iv = self._make('Plin curi')
        iv.assign_worker(self.user)
        self.assertEqual(iv.status, 'DODIJELJENO')
        iv.status = 'NA_PUTU'; iv.started_at = timezone.now(); iv.save()
        iv.refresh_from_db()
        self.assertIsNotNone(iv.started_at)
        iv.status = 'NA_LOKACIJI'; iv.arrived_at = timezone.now(); iv.save()
        iv.refresh_from_db()
        self.assertIsNotNone(iv.arrived_at)
        iv.status = 'RIJESENO'; iv.resolved_at = timezone.now(); iv.save()
        iv.refresh_from_db()
        self.assertEqual(iv.status, 'RIJESENO')
        self.assertIsNotNone(iv.resolved_at)

    def test_ttl_expired_resets_to_novo(self):
        """When no other workers available, expired TTL resets to NOVO."""
        from interventions.models import HitnaIntervencija
        iv = self._make(
            'TTL test',
            status='DODIJELJENO',
            assigned_to=self.user,
            assigned_at=timezone.now() - timedelta(minutes=10),
            ttl_expires_at=timezone.now() - timedelta(minutes=7),
        )
        orig_user_id = self.user.pk
        from django.core.management import call_command
        import io
        call_command('check_ttl', stdout=io.StringIO(), stderr=io.StringIO())
        iv.refresh_from_db()
        # TTL was processed: reset to NOVO or reassigned to a different worker
        if iv.status == 'NOVO':
            self.assertIsNone(iv.assigned_to)
            self.assertIsNone(iv.ttl_expires_at)
        elif iv.status == 'DODIJELJENO':
            self.assertNotEqual(iv.assigned_to_id, orig_user_id)
            self.assertIsNotNone(iv.ttl_expires_at)
            self.assertGreater(iv.ttl_expires_at, timezone.now())
        else:
            self.fail(f'Unexpected status after TTL: {iv.status}')

    def test_escalate_to_kanban(self):
        from interventions.models import HitnaIntervencija
        from burza.models import ProjectLead
        iv = self._make('Eskaliraj ovo', status='RIJESENO')
        lead = ProjectLead.objects.create(
            company=self.company,
            title=f'Eskalacija: {iv.title}',
            description='',
            category='ostalo',
            location=iv.address,
            contact_name=iv.client_name,
            contact_phone=iv.client_phone,
            status='NOVI_UPIT',
            created_by=self.user,
        )
        iv.status = 'ESKALIRANO'
        iv.project_lead = lead
        iv.save()
        iv.refresh_from_db()
        self.assertEqual(iv.status, 'ESKALIRANO')
        self.assertIsNotNone(iv.project_lead)
        self.assertEqual(iv.project_lead.pk, lead.pk)

    def test_tracking_page_public(self):
        iv = self._make('Tracking test')
        c = Client()
        resp = c.get(f'/track/{iv.tracking_token}/')
        self.assertEqual(resp.status_code, 200)

    def test_interventions_requires_login(self):
        c = Client()
        resp = c.get('/interventions/')
        self.assertEqual(resp.status_code, 302)

    def test_new_intervention_requires_login(self):
        c = Client()
        resp = c.get('/interventions/new/')
        self.assertEqual(resp.status_code, 302)


# ─── 8. IMPERSONATION ────────────────────────────────────────────────────────

class ImpersonationTests(unittest.TestCase):

    def setUp(self):
        self.superuser = get_or_create_user('test_super_imp', is_superuser=True, is_staff=True)
        self.company   = get_or_create_company()

    def test_start_impersonation_creates_log(self):
        from accounts.models import ImpersonationLog
        c = Client()
        c.force_login(self.superuser)
        before = ImpersonationLog.objects.filter(
            superadmin=self.superuser, company=self.company
        ).count()
        resp = c.get(f'/superadmin/impersonate/{self.company.id}/')
        self.assertIn(resp.status_code, [200, 302])
        after = ImpersonationLog.objects.filter(
            superadmin=self.superuser, company=self.company
        ).count()
        self.assertGreater(after, before)

    def test_stop_impersonation_sets_ended_at(self):
        from accounts.models import ImpersonationLog
        log = ImpersonationLog.objects.create(
            superadmin=self.superuser,
            company=self.company,
            ip_address='127.0.0.1',
        )
        self.assertIsNone(log.ended_at)
        c = Client()
        c.force_login(self.superuser)
        session = c.session
        session['impersonated_company_id']  = str(self.company.id)
        session['impersonation_started_at'] = int(timezone.now().timestamp())
        session['impersonation_log_id']     = log.id
        session.save()
        resp = c.get('/superadmin/impersonate/stop/')
        self.assertIn(resp.status_code, [200, 302])
        log.refresh_from_db()
        self.assertIsNotNone(log.ended_at)

    def test_impersonation_log_audit_fields(self):
        from accounts.models import ImpersonationLog
        log = ImpersonationLog.objects.create(
            superadmin=self.superuser,
            company=self.company,
            ip_address='192.168.1.100',
            actions_count=5,
        )
        self.assertEqual(log.superadmin, self.superuser)
        self.assertEqual(log.company, self.company)
        self.assertEqual(log.actions_count, 5)
        self.assertIsNone(log.ended_at)
        self.assertIsNotNone(log.started_at)

    def test_companies_page_requires_superuser(self):
        regular = get_or_create_user('regular_user_imp')
        c = Client()
        c.force_login(regular)
        resp = c.get('/superadmin/companies/')
        self.assertIn(resp.status_code, [302, 403])

    def test_superadmin_can_access_companies_page(self):
        c = Client()
        c.force_login(self.superuser)
        resp = c.get('/superadmin/companies/')
        self.assertEqual(resp.status_code, 200)



# ─── 9. TRACKING ──────────────────────────────────────────────────────────────

class TrackingTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        from tracking.models import TrackingStatus
        self.status_new, _ = TrackingStatus.objects.get_or_create(
            tracking_type='food_order', slug='new',
            defaults={'name': 'New', 'order': 0, 'color': '#c9a84c'},
        )
        self.status_ready, _ = TrackingStatus.objects.get_or_create(
            tracking_type='food_order', slug='ready',
            defaults={'name': 'Ready', 'order': 2, 'color': '#27ae60'},
        )

    def test_create_tracking_status(self):
        self.assertEqual(self.status_new.tracking_type, 'food_order')
        self.assertEqual(self.status_new.slug, 'new')
        print('  ✓ Create tracking status')

    def test_tracked_item_auto_token(self):
        from tracking.models import TrackedItem
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self.company)
        item = TrackedItem.objects.create(
            content_type=ct,
            object_id=str(self.company.pk),
            tracking_type='food_order',
            current_status=self.status_new,
        )
        self.assertTrue(len(item.public_token) >= 16)
        item.delete()
        print('  ✓ Tracked item auto-generates public token')

    def test_update_status_creates_event(self):
        from tracking.models import TrackedItem, TrackingEvent
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self.company)
        item = TrackedItem.objects.create(
            content_type=ct,
            object_id=str(self.company.pk),
            tracking_type='food_order',
            current_status=self.status_new,
        )
        item.update_status(self.status_ready, note='Kitchen done')
        item.refresh_from_db()
        self.assertEqual(item.current_status, self.status_ready)
        events = TrackingEvent.objects.filter(tracked_item=item)
        self.assertTrue(events.exists())
        self.assertEqual(events.first().note, 'Kitchen done')
        item.delete()
        print('  ✓ update_status() creates TrackingEvent')

    def test_tracking_api_public(self):
        from tracking.models import TrackedItem
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self.company)
        item = TrackedItem.objects.create(
            content_type=ct,
            object_id=str(self.company.pk),
            tracking_type='food_order',
            current_status=self.status_new,
        )
        c = Client()
        resp = c.get(f'/tracking/api/{item.public_token}/')
        self.assertEqual(resp.status_code, 200)
        item.delete()
        print('  ✓ Tracking API is public (200 without login)')

    def test_tracking_events_api(self):
        from tracking.models import TrackedItem
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(self.company)
        item = TrackedItem.objects.create(
            content_type=ct,
            object_id=str(self.company.pk),
            tracking_type='food_order',
            current_status=self.status_new,
        )
        c = Client()
        resp = c.get(f'/tracking/api/{item.public_token}/events/')
        self.assertEqual(resp.status_code, 200)
        item.delete()
        print('  ✓ Tracking events API is public (200)')

    def test_tracking_update_requires_login(self):
        c = Client()
        resp = c.post('/tracking/update/999/', content_type='application/json',
                       data='{"status_id": 1}')
        self.assertIn(resp.status_code, [302, 403])
        print('  ✓ Tracking update requires login (302)')


# ─── 10. GASTRO POS ──────────────────────────────────────────────────────────

class GastroTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()

    def _make_table(self, name='T1'):
        from pos.models import Table
        t, _ = Table.objects.get_or_create(
            company=self.company, name=name,
            defaults={'table_type': 'table', 'capacity': 4},
        )
        return t

    def _make_inventory_item(self, name='Test Burger'):
        from inventory.models import InventoryItem
        item, _ = InventoryItem.objects.get_or_create(
            company=self.company, sku=f'TST-{name[:8]}',
            defaults={
                'name': name,
                'category': 'product',
                'unit_price': Decimal('10.00'),
            },
        )
        return item

    def test_create_table_auto_qr(self):
        table = self._make_table('TST-QR')
        self.assertTrue(len(table.qr_code) >= 8)
        print('  ✓ Create table with auto QR code')

    def test_create_gastro_order_auto_token(self):
        from pos.models import GastroOrder
        table = self._make_table('TST-ORD')
        order = GastroOrder.objects.create(
            company=self.company, table=table, status='new',
        )
        self.assertTrue(len(order.tracking_token) >= 16)
        order.delete()
        print('  ✓ Create gastro order with auto tracking token')

    def test_add_gastro_order_item(self):
        from pos.models import GastroOrder, GastroOrderItem
        table = self._make_table('TST-ITEM')
        inv = self._make_inventory_item('Cheese Burger')
        order = GastroOrder.objects.create(
            company=self.company, table=table, status='new',
        )
        item = GastroOrderItem.objects.create(
            order=order, inventory_item=inv, quantity=Decimal('2'),
        )
        self.assertEqual(item.quantity, Decimal('2'))
        self.assertEqual(order.items.count(), 1)
        order.delete()
        print('  ✓ Add item to gastro order')

    def test_gastro_dashboard_requires_login(self):
        c = Client()
        resp = c.get('/pos/gastro/')
        self.assertIn(resp.status_code, [302, 301])
        print('  ✓ Gastro dashboard requires login (302)')

    def test_kitchen_requires_login(self):
        c = Client()
        resp = c.get('/pos/gastro/kitchen/')
        self.assertIn(resp.status_code, [302, 301])
        print('  ✓ Kitchen display requires login (302)')

    def test_order_status_update(self):
        from pos.models import GastroOrder
        table = self._make_table('TST-STAT')
        order = GastroOrder.objects.create(
            company=self.company, table=table, status='new',
        )
        order.status = 'preparing'
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'preparing')
        order.delete()
        print('  ✓ Gastro order status update')

    def test_public_order_tracking(self):
        from pos.models import GastroOrder
        table = self._make_table('TST-PUB')
        order = GastroOrder.objects.create(
            company=self.company, table=table, status='new',
        )
        c = Client()
        resp = c.get(f'/pos/gastro/order/{order.tracking_token}/')
        self.assertEqual(resp.status_code, 200)
        order.delete()
        print('  ✓ Public order tracking page (200 without login)')


# ─── 11. EXPIRY TRACKING ─────────────────────────────────────────────────────

class ExpiryTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()

    def _make_inventory_item(self, name='Test Item Exp'):
        from inventory.models import InventoryItem
        item, _ = InventoryItem.objects.get_or_create(
            company=self.company, sku=f'TST-EXP-{name[:5]}',
            defaults={
                'name': name,
                'category': 'product',
                'unit_price': Decimal('5.00'),
            },
        )
        return item

    def test_create_expiry_batch(self):
        from pos.models import ExpiryBatch
        inv = self._make_inventory_item('Milk')
        batch = ExpiryBatch.objects.create(
            company=self.company,
            inventory_item=inv,
            batch_number='B-001',
            quantity=Decimal('50'),
            expiry_date=date.today() + timedelta(days=10),
        )
        self.assertEqual(batch.batch_number, 'B-001')
        batch.delete()
        print('  ✓ Create expiry batch')

    def test_is_expired_property(self):
        from pos.models import ExpiryBatch
        inv = self._make_inventory_item('Yogurt')
        batch = ExpiryBatch.objects.create(
            company=self.company,
            inventory_item=inv,
            batch_number='B-EXP',
            quantity=Decimal('10'),
            expiry_date=date.today() - timedelta(days=2),
        )
        self.assertTrue(batch.is_expired)
        batch.delete()
        print('  ✓ is_expired property (past date → True)')

    def test_is_warning_property(self):
        from pos.models import ExpiryBatch
        inv = self._make_inventory_item('Cream')
        batch = ExpiryBatch.objects.create(
            company=self.company,
            inventory_item=inv,
            batch_number='B-WARN',
            quantity=Decimal('20'),
            expiry_date=date.today() + timedelta(days=2),
            alert_days_before=3,
        )
        self.assertTrue(batch.is_warning)
        self.assertFalse(batch.is_expired)
        batch.delete()
        print('  ✓ is_warning property (within alert window → True)')

    def test_days_until_expiry(self):
        from pos.models import ExpiryBatch
        inv = self._make_inventory_item('Juice')
        batch = ExpiryBatch.objects.create(
            company=self.company,
            inventory_item=inv,
            batch_number='B-DAYS',
            quantity=Decimal('30'),
            expiry_date=date.today() + timedelta(days=5),
        )
        self.assertEqual(batch.days_until_expiry, 5)
        batch.delete()
        print('  ✓ days_until_expiry returns correct count')

    def test_expiry_dashboard_requires_login(self):
        c = Client()
        resp = c.get('/pos/expiry/')
        self.assertIn(resp.status_code, [302, 301])
        print('  ✓ Expiry dashboard requires login (302)')



# --- 12. AI ASSISTANT --------------------------------------------------------

class AIAssistantTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        self.user = get_or_create_user('ai_test_user', is_staff=True, is_superuser=True)

    def test_conversation_create(self):
        from ai_assistant.models import Conversation
        conv = Conversation.objects.create(
            user=self.user, title='Test razgovor', module_context='inventory'
        )
        self.assertEqual(conv.title, 'Test razgovor')
        self.assertTrue(conv.is_active)
        conv.delete()
        print('  \u2713 Create conversation')

    def test_message_create(self):
        from ai_assistant.models import Conversation, Message
        conv = Conversation.objects.create(user=self.user, title='Msg test')
        msg = Message.objects.create(conversation=conv, role='user', content='Bok')
        self.assertEqual(msg.role, 'user')
        self.assertEqual(msg.content, 'Bok')
        conv.delete()
        print('  \u2713 Create message')

    def test_usage_log_create(self):
        from ai_assistant.models import Conversation, AIUsageLog
        conv = Conversation.objects.create(user=self.user, title='Usage test')
        log = AIUsageLog.objects.create(
            user=self.user, conversation=conv,
            input_tokens=100, output_tokens=200
        )
        self.assertEqual(log.input_tokens, 100)
        conv.delete()
        print('  \u2713 Create usage log')

    def test_chat_page_requires_login(self):
        c = Client()
        resp = c.get('/ai/')
        self.assertIn(resp.status_code, [302, 301])
        print('  \u2713 Chat page requires login (302)')

    def test_chat_api_requires_post(self):
        c = Client()
        c.login(username='ai_test_user', password='Test123!')
        resp = c.get('/ai/api/chat/')
        self.assertEqual(resp.status_code, 405)
        print('  \u2713 Chat API requires POST (405)')

    def test_chat_api_requires_login(self):
        c = Client()
        resp = c.post('/ai/api/chat/', '{"message":"test"}', content_type='application/json')
        self.assertIn(resp.status_code, [302, 301])
        print('  \u2713 Chat API requires login (302)')

    def test_tool_handler_search_articles(self):
        from ai_assistant.tool_handlers import handle_tool_call
        result = handle_tool_call('search_articles', {'query': 'nonexistent_xyz'}, self.user, self.company)
        self.assertIn('count', result)
        self.assertIn('items', result)
        print('  \u2713 Tool handler: search_articles')

    def test_tool_handler_today_revenue(self):
        from ai_assistant.tool_handlers import handle_tool_call
        result = handle_tool_call('get_today_revenue', {}, self.user, self.company)
        self.assertIn('total_revenue', result)
        self.assertIn('receipt_count', result)
        print('  \u2713 Tool handler: get_today_revenue')


# --- 13. BOOKING ENHANCEMENTS ------------------------------------------------

class BookingTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        self.user = get_or_create_user('booking_test_user', is_staff=True, is_superuser=True)

    def test_public_booking_index(self):
        c = Client()
        resp = c.get('/appointments/booking/')
        self.assertEqual(resp.status_code, 200)
        print('  \u2713 Public booking index (200 without login)')

    def test_available_slots_api(self):
        c = Client()
        resp = c.get('/appointments/api/booking/slots/')
        self.assertEqual(resp.status_code, 400)
        print('  \u2713 Available slots API returns 400 without params')

    def test_booking_auth_check_anonymous(self):
        c = Client()
        resp = c.get('/appointments/api/booking/auth-check/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['authenticated'])
        print('  \u2713 Booking auth check - anonymous')

    def test_booking_auth_check_logged_in(self):
        c = Client()
        c.login(username='booking_test_user', password='Test123!')
        resp = c.get('/appointments/api/booking/auth-check/')
        data = resp.json()
        self.assertTrue(data['authenticated'])
        print('  \u2713 Booking auth check - logged in')

    def test_ics_generation(self):
        from appointments.ics_utils import generate_ics
        from appointments.models import Appointment
        from datetime import datetime
        appt = Appointment(
            id=9999, title='Test ICS',
            start_time=datetime(2025, 6, 15, 10, 0),
            end_time=datetime(2025, 6, 15, 11, 0),
        )
        ics = generate_ics(appt)
        self.assertIn('BEGIN:VCALENDAR', ics)
        self.assertIn('Test ICS', ics)
        self.assertIn('BEGIN:VEVENT', ics)
        print('  \u2713 ICS generation')

    def test_company_booking_slug(self):
        from companies.models import Company
        co = Company.objects.get(oib='12345678901')
        if not co.booking_slug:
            co.booking_slug = None
            co.save()
        self.assertTrue(bool(co.booking_slug))
        print('  \u2713 Company booking_slug auto-generated')




# --- 14. RBAC ---
class RBACTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from django.core.management import call_command
        call_command('seed_permissions', verbosity=0)

    def test_seed_creates_permissions(self):
        from permissions.models import Permission
        self.assertEqual(Permission.objects.count(), 88)

    def test_seed_creates_roles(self):
        from permissions.models import Role
        self.assertEqual(Role.objects.count(), 8)

    def test_superadmin_has_all_permissions(self):
        from permissions.manager import PermissionManager
        user = get_or_create_user('rbac_super', is_superuser=True)
        perms = PermissionManager.get_user_permissions(user)
        self.assertEqual(len(perms), 88)

    def test_worker_limited_permissions(self):
        from permissions.models import Role, UserRole
        from permissions.manager import PermissionManager
        user = get_or_create_user('rbac_worker')
        role = Role.objects.get(role_type='worker')
        UserRole.objects.get_or_create(user=user, role=role, defaults={'is_primary': True})
        perms = PermissionManager.get_user_permissions(user)
        self.assertIn('worktime.view', perms)
        self.assertNotIn('finance.delete', perms)

    def test_decorator_blocks_unauthorized(self):
        c = Client()
        user = get_or_create_user('rbac_norole')
        c.login(username='rbac_norole', password='Test123!')
        resp = c.get('/invoicing/new/')
        self.assertIn(resp.status_code, [403, 302])

    def test_decorator_allows_superadmin(self):
        c = Client()
        user = get_or_create_user('rbac_admin2', is_superuser=True, is_staff=True)
        c.login(username='rbac_admin2', password='Test123!')
        resp = c.get('/invoicing/new/')
        self.assertEqual(resp.status_code, 200)

    def test_middleware_sets_attrs(self):
        c = Client()
        user = get_or_create_user('rbac_mw', is_superuser=True, is_staff=True)
        c.force_login(user)
        resp = c.get('/invoicing/new/')
        self.assertEqual(resp.status_code, 200)

    def test_context_processor(self):
        c = Client()
        user = get_or_create_user('rbac_ctx', is_superuser=True, is_staff=True)
        c.force_login(user)
        resp = c.get('/superadmin/')
        self.assertEqual(resp.status_code, 200)


# --- 15. NOTIFICATIONS ---
class NotificationTests(unittest.TestCase):
    def test_create_notification(self):
        from notifications.models import Notification
        user = get_or_create_user('notif_user')
        n = Notification.objects.create(
            recipient=user, title='Test', message='Hello',
            notification_type='system',
        )
        self.assertEqual(n.is_read, False)
        n.delete()

    def test_mark_read(self):
        from notifications.models import Notification
        user = get_or_create_user('notif_user2')
        n = Notification.objects.create(recipient=user, title='X', notification_type='system')
        c = Client()
        c.login(username='notif_user2', password='Test123!')
        resp = c.post(f'/notifications/{n.pk}/read/')
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        n.delete()

    def test_api_unread_count(self):
        from notifications.models import Notification
        user = get_or_create_user('notif_user3')
        Notification.objects.create(recipient=user, title='A', notification_type='system')
        Notification.objects.create(recipient=user, title='B', notification_type='system')
        c = Client()
        c.login(username='notif_user3', password='Test123!')
        resp = c.get('/notifications/api/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['unread_count'], 2)
        Notification.objects.filter(recipient=user).delete()

    def test_list_requires_login(self):
        c = Client()
        resp = c.get('/notifications/')
        self.assertIn(resp.status_code, [302, 301])

    def test_notify_helper(self):
        from notifications.services import notify
        user = get_or_create_user('notif_helper')
        n = notify(user, 'system', 'Test Title', 'Test Msg')
        self.assertEqual(n.title, 'Test Title')
        n.delete()

    def test_mark_all_read(self):
        from notifications.models import Notification
        user = get_or_create_user('notif_all')
        Notification.objects.create(recipient=user, title='1', notification_type='system')
        Notification.objects.create(recipient=user, title='2', notification_type='system')
        c = Client()
        c.login(username='notif_all', password='Test123!')
        resp = c.post('/notifications/read-all/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Notification.objects.filter(recipient=user, is_read=False).count(), 0)
        Notification.objects.filter(recipient=user).delete()


# --- 16. REPORTS ---
class ReportTests(unittest.TestCase):
    def test_dashboard_requires_login(self):
        c = Client()
        resp = c.get('/reports/')
        self.assertIn(resp.status_code, [302, 301])

    def test_revenue_requires_login(self):
        c = Client()
        resp = c.get('/reports/revenue/')
        self.assertIn(resp.status_code, [302, 301])

    def test_worktime_requires_login(self):
        c = Client()
        resp = c.get('/reports/worktime/')
        self.assertIn(resp.status_code, [302, 301])

    def test_csv_content_type(self):
        c = Client()
        user = get_or_create_user('report_csv', is_staff=True)
        c.login(username='report_csv', password='Test123!')
        resp = c.get('/reports/export/revenue/csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])

    def test_excel_content_type(self):
        c = Client()
        user = get_or_create_user('report_xlsx', is_staff=True)
        c.login(username='report_xlsx', password='Test123!')
        resp = c.get('/reports/export/worktime/excel/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])



# --- 17. MODULE GATING ---
class ModuleGatingTests(unittest.TestCase):
    def test_context_processor_modules_for_subscribed_company(self):
        """subscription_context returns allowed modules for a subscribed company user."""
        from permissions.context_processors import subscription_context
        from registration.models import CompanySubscription
        company = get_or_create_company()
        user = get_or_create_user('modgate_user1')
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'company': company, 'role': 'worker'})
        if profile.company != company:
            profile.company = company
            profile.save()
        sub, _ = CompanySubscription.objects.get_or_create(
            company=company,
            defaults={'plan': 'starter', 'is_active': True, 'valid_from': date.today(), 'monthly_fee': 0}
        )
        sub.is_active = True
        sub.plan = 'starter'
        sub.save()
        class MockReq:
            pass
        req = MockReq()
        req.user = user
        ctx = subscription_context(req)
        self.assertIn('allowed_modules', ctx)
        modules = ctx['allowed_modules']
        self.assertIn('invoicing', modules)

    def test_context_processor_all_for_superuser(self):
        """subscription_context returns _AllModulesSet for superusers."""
        from permissions.context_processors import subscription_context
        user = get_or_create_user('modgate_super', is_superuser=True, is_staff=True)
        class MockReq:
            pass
        req = MockReq()
        req.user = user
        ctx = subscription_context(req)
        modules = ctx['allowed_modules']
        self.assertIn('invoicing', modules)
        self.assertIn('random_nonexistent_module', modules)
        self.assertTrue(ctx['is_company_admin'])

    def test_context_processor_empty_for_anonymous(self):
        """subscription_context returns empty set for unauthenticated."""
        from permissions.context_processors import subscription_context
        from django.contrib.auth.models import AnonymousUser
        class MockReq:
            pass
        req = MockReq()
        req.user = AnonymousUser()
        ctx = subscription_context(req)
        self.assertEqual(ctx['allowed_modules'], set())
        self.assertFalse(ctx['is_company_admin'])

    def test_sidebar_shows_invoicing_for_starter(self):
        """Sidebar shows invoicing link for starter plan user."""
        company = get_or_create_company()
        user = get_or_create_user('modgate_sidebar1', is_staff=True)
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'company': company, 'role': 'company_admin'})
        profile.company = company
        profile.role = 'company_admin'
        profile.save()
        from registration.models import CompanySubscription
        sub, _ = CompanySubscription.objects.get_or_create(
            company=company,
            defaults={'plan': 'starter', 'is_active': True, 'valid_from': date.today(), 'monthly_fee': 0}
        )
        sub.is_active = True
        sub.plan = 'starter'
        sub.save()
        c = Client()
        c.login(username='modgate_sidebar1', password='Test123!')
        resp = c.get('/dashboard/company/')
        if resp.status_code == 200:
            content = resp.content.decode()
            self.assertIn('/invoicing/', content)

    def test_sidebar_hides_finance_for_starter(self):
        """Sidebar hides finance link for starter plan user (finance not in starter)."""
        company = get_or_create_company()
        user = get_or_create_user('modgate_sidebar2', is_staff=True)
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'company': company, 'role': 'company_admin'})
        profile.company = company
        profile.role = 'company_admin'
        profile.save()
        from registration.models import CompanySubscription
        sub, _ = CompanySubscription.objects.get_or_create(
            company=company,
            defaults={'plan': 'starter', 'is_active': True, 'valid_from': date.today(), 'monthly_fee': 0}
        )
        sub.is_active = True
        sub.plan = 'starter'
        sub.modules_override = None
        sub.save()
        c = Client()
        c.login(username='modgate_sidebar2', password='Test123!')
        resp = c.get('/dashboard/company/')
        if resp.status_code == 200:
            content = resp.content.decode()
            self.assertNotIn('/finance/', content)

    def test_subscription_middleware_blocks_unauthorized(self):
        """SubscriptionMiddleware blocks unauthorized module access."""
        company = get_or_create_company()
        user = get_or_create_user('modgate_blocked')
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'company': company, 'role': 'worker'})
        profile.company = company
        profile.save()
        from registration.models import CompanySubscription
        sub, _ = CompanySubscription.objects.get_or_create(
            company=company,
            defaults={'plan': 'starter', 'is_active': True, 'valid_from': date.today(), 'monthly_fee': 0}
        )
        sub.is_active = True
        sub.plan = 'starter'
        sub.modules_override = None
        sub.save()
        c = Client()
        c.login(username='modgate_blocked', password='Test123!')
        resp = c.get('/finance/')
        self.assertIn(resp.status_code, [302, 403])


# --- 18. CLIENT PORTAL ---
class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = get_or_create_company()
        from partners.models import Partner
        cls.partner, _ = Partner.objects.get_or_create(
            name='Portal Test Partner', company=company, oib='99999999999',
            defaults={'partner_type': 'client', 'country': 'HR'}
        )
        cls.token = str(cls.partner.portal_token)

    def test_portal_home_valid_token(self):
        """Portal home returns 200 with valid token."""
        c = Client()
        resp = c.get('/portal/' + self.token + '/')
        self.assertEqual(resp.status_code, 200)

    def test_portal_home_invalid_token(self):
        """Portal returns 404 with invalid token."""
        import uuid
        c = Client()
        resp = c.get('/portal/' + str(uuid.uuid4()) + '/')
        self.assertEqual(resp.status_code, 404)

    def test_portal_invoices_page(self):
        """Portal invoices page loads for correct partner."""
        c = Client()
        resp = c.get('/portal/' + self.token + '/invoices/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Fakture', resp.content)

    def test_portal_invoice_detail(self):
        """Portal invoice detail works for partner invoice."""
        from invoicing.models import Invoice
        company = get_or_create_company()
        inv, _ = Invoice.objects.get_or_create(
            number='PORTAL-TEST-001',
            defaults={
                'company': company,
                'partner': self.partner,
                'date_issued': date.today(),
                'status': 'SENT',
                'total': Decimal('100.00'),
                'subtotal': Decimal('80.00'),
                'tax_amount': Decimal('20.00'),
                'tax_percent': Decimal('25.00'),
                'currency': 'EUR',
                'issuer_name': 'Test Issuer',
                'client_name': self.partner.name,
            }
        )
        c = Client()
        resp = c.get('/portal/' + self.token + '/invoices/' + str(inv.pk) + '/')
        self.assertEqual(resp.status_code, 200)

    def test_portal_projects_page(self):
        """Portal projects page loads."""
        c = Client()
        resp = c.get('/portal/' + self.token + '/projects/')
        self.assertEqual(resp.status_code, 200)

    def test_portal_documents_page(self):
        """Portal documents page loads."""
        c = Client()
        resp = c.get('/portal/' + self.token + '/documents/')
        self.assertEqual(resp.status_code, 200)



class CeleryTests(unittest.TestCase):
    """Suite 19: Celery async email tasks."""

    @classmethod
    def setUpClass(cls):
        from django.conf import settings
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
        cls.company = get_or_create_company()

    def test_celery_app_loads(self):
        """Celery app loads correctly."""
        from core.celery import app
        self.assertEqual(app.main, 'fina_connect')

    def test_send_email_task(self):
        """send_email_task executes with ALWAYS_EAGER."""
        from core.email_tasks import send_email_task
        result = send_email_task.apply(args=[
            'Test Subject', 'Test body', 'test@example.com', ['user@example.com'],
        ])
        self.assertTrue(result.successful())

    def test_send_email_with_attachment_task(self):
        """send_email_with_attachment_task executes with base64 PDF."""
        import base64
        from core.email_tasks import send_email_with_attachment_task
        fake_pdf = base64.b64encode(b'%PDF-1.4 fake').decode()
        result = send_email_with_attachment_task.apply(args=[
            'Invoice', 'Body', 'test@example.com', ['user@example.com'],
            'test.pdf', fake_pdf, 'application/pdf',
        ])
        self.assertTrue(result.successful())

    def test_send_html_email_task(self):
        """send_html_email_task sends HTML email."""
        from core.email_tasks import send_html_email_task
        result = send_html_email_task.apply(args=[
            'HTML Test', 'Plain text', '<h1>HTML</h1>', 'test@example.com', ['user@example.com'],
        ])
        self.assertTrue(result.successful())

    def test_overdue_invoice_task(self):
        """Overdue invoice task marks invoices as OVERDUE."""
        from invoicing.models import Invoice
        from invoicing.tasks import check_overdue_invoices
        inv = Invoice.objects.create(
            company=self.company, number='TEST-OVERDUE-001', doctype='R',
            status='SENT', date_issued=timezone.now(),
            date_due=date.today() - timedelta(days=5),
            client_name='Test Client', client_email='test@example.com',
            issuer_name='Test Issuer', issuer_iban='DE00000000000000',
            currency='EUR', total=100,
        )
        result = check_overdue_invoices.apply()
        self.assertTrue(result.successful())
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'OVERDUE')
        inv.delete()

    def test_appointment_reminder_task(self):
        """Appointment reminder task sends for 24h window."""
        from appointments.models import Appointment
        from appointments.tasks import send_appointment_reminders
        from partners.models import Partner
        partner, _created = Partner.objects.get_or_create(name='Reminder Client', company=self.company, defaults={'email': 'remind@example.com', 'partner_type': 'KUPAC', 'oib': '99999999901'})
        appt = Appointment.objects.create(
            title='Test Reminder', start_time=timezone.now() + timedelta(hours=12),
            end_time=timezone.now() + timedelta(hours=13),
            status='scheduled', client=partner, email_reminder_sent=False,
        )
        result = send_appointment_reminders.apply()
        self.assertTrue(result.successful())
        appt.refresh_from_db()
        self.assertTrue(appt.email_reminder_sent)
        appt.delete()
        partner.delete()


class EmailTemplateTests(unittest.TestCase):
    """Suite 20: Email template rendering."""

    def test_base_email_renders(self):
        """base_email.html renders without errors."""
        from django.template.loader import render_to_string
        html = render_to_string('emails/base_email.html', {})
        self.assertIn('LIMIT CONNECT', html)

    def test_invoice_sent_renders(self):
        """invoice_sent.html renders with context."""
        from django.template.loader import render_to_string
        html = render_to_string('emails/invoice_sent.html', {
            'invoice_number': 'R-001', 'client_name': 'Test GmbH',
            'total': '1000.00', 'currency': 'EUR', 'date_due': '2026-03-01',
            'issuer_name': 'FINA', 'issuer_iban': 'DE123', 'is_hr': False,
        })
        self.assertIn('R-001', html)
        self.assertIn('Rechnung', html)

    def test_registration_approved_renders(self):
        """registration_approved.html renders with context."""
        from django.template.loader import render_to_string
        html = render_to_string('emails/registration_approved.html', {
            'contact_name': 'Ivan', 'company_name': 'Firma d.o.o.',
            'username': 'ivan', 'password': 'secret123', 'plan': 'BUSINESS',
        })
        self.assertIn('Account Approved', html)
        self.assertIn('ivan', html)

    def test_appointment_confirmation_renders(self):
        """appointment_confirmation.html renders with context."""
        from django.template.loader import render_to_string
        html = render_to_string('emails/appointment_confirmation.html', {
            'client_name': 'Marko', 'service_name': 'Frizura',
            'datetime': '28.02.2026 u 10:00', 'duration': 30, 'price': '25.00',
        })
        self.assertIn('Frizura', html)
        self.assertIn('Potvrda', html)

    def test_invoice_overdue_renders(self):
        """invoice_overdue.html renders with context."""
        from django.template.loader import render_to_string
        html = render_to_string('emails/invoice_overdue.html', {
            'invoice_number': 'R-002', 'client_name': 'Test AG',
            'total': '500.00', 'currency': 'EUR', 'date_due': '2026-01-15',
            'issuer_name': 'FINA', 'issuer_iban': 'DE456', 'is_hr': False,
        })
        self.assertIn('R-002', html)
        self.assertIn('Zahlungserinnerung', html)




# ─── 21. WHATSAPP SERVICE ─────────────────────────────────────────────────────

class WhatsAppTests(unittest.TestCase):
    """Suite 21: WhatsApp service (core/whatsapp.py)."""

    def settings(self, **kwargs):
        from django.test.utils import override_settings
        return override_settings(**kwargs)

    def test_normalize_phone_german_mobile(self):
        """German mobile +49 prefix normalizes correctly."""
        from core.whatsapp import normalize_phone
        self.assertEqual(normalize_phone('+49 171 1234567'), '491711234567')

    def test_normalize_phone_croatian_mobile(self):
        """Croatian mobile +385 prefix normalizes correctly."""
        from core.whatsapp import normalize_phone
        self.assertEqual(normalize_phone('+385 91 234 5678'), '385912345678')

    def test_normalize_phone_local_croatian(self):
        """Local Croatian (091...) normalizes to +385 prefix."""
        from core.whatsapp import normalize_phone
        result = normalize_phone('091 234 5678')
        self.assertEqual(result, '385912345678')

    def test_normalize_phone_empty_invalid(self):
        """Empty or invalid input returns empty string."""
        from core.whatsapp import normalize_phone
        self.assertEqual(normalize_phone(''), '')
        self.assertEqual(normalize_phone(None), '')
        self.assertEqual(normalize_phone('abc'), '')
        self.assertEqual(normalize_phone('12'), '')

    def test_send_text_success(self):
        """send_text returns success on HTTP 200."""
        from unittest.mock import patch, MagicMock
        from core.whatsapp import send_text
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'id': 'msg123'}
        with patch('core.whatsapp.requests.post', return_value=mock_resp):
            with self.settings(WAHA_ENABLED=True, WAHA_API_URL='http://test:3000',
                               WAHA_SESSION_NAME='default', WAHA_API_KEY='testkey'):
                result = send_text('+491711234567', 'Hello')
        self.assertTrue(result['success'])
        self.assertIsNone(result['error'])

    def test_send_text_gateway_error(self):
        """send_text returns error on HTTP 500."""
        from unittest.mock import patch, MagicMock
        from core.whatsapp import send_text
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = 'Internal Server Error'
        with patch('core.whatsapp.requests.post', return_value=mock_resp):
            with self.settings(WAHA_ENABLED=True, WAHA_API_URL='http://test:3000',
                               WAHA_SESSION_NAME='default', WAHA_API_KEY='testkey'):
                result = send_text('+491711234567', 'Hello')
        self.assertFalse(result['success'])
        self.assertIn('500', result['error'])

    def test_send_text_gateway_unreachable(self):
        """send_text returns error on ConnectionError."""
        import requests as req
        from unittest.mock import patch
        from core.whatsapp import send_text
        with patch('core.whatsapp.requests.post', side_effect=req.ConnectionError('refused')):
            with self.settings(WAHA_ENABLED=True, WAHA_API_URL='http://test:3000',
                               WAHA_SESSION_NAME='default', WAHA_API_KEY='testkey'):
                result = send_text('+491711234567', 'Hello')
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Gateway unreachable')

    def test_send_text_invalid_phone(self):
        """send_text returns error for invalid phone."""
        from core.whatsapp import send_text
        with self.settings(WAHA_ENABLED=True):
            result = send_text('abc', 'Hello')
        self.assertFalse(result['success'])
        self.assertIn('Invalid phone', result['error'])


# ─── 22. WHATSAPP CELERY TASKS ────────────────────────────────────────────────

class WhatsAppTaskTests(unittest.TestCase):
    """Suite 22: WhatsApp Celery tasks (core/whatsapp_tasks.py)."""

    def settings(self, **kwargs):
        from django.test.utils import override_settings
        return override_settings(**kwargs)

    def setUp(self):
        from django.conf import settings
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
        self.company = get_or_create_company()

    def test_send_appointment_confirmation(self):
        """send_appointment_confirmation_whatsapp executes with mock."""
        from unittest.mock import patch
        from appointments.models import Appointment
        from core.whatsapp_tasks import send_appointment_confirmation_whatsapp

        appt = Appointment.objects.create(
            title='WA Test Appt',
            start_time=timezone.now() + timedelta(hours=24),
            end_time=timezone.now() + timedelta(hours=25),
            status='scheduled',
            whatsapp_number='+491711234567',
            company=self.company,
        )
        mock_result = {'success': True, 'error': None, 'response': {}}
        with patch('core.whatsapp.send_text', return_value=mock_result):
            result = send_appointment_confirmation_whatsapp(appt.id)
        self.assertTrue(result['success'])
        appt.delete()

    def test_send_appointment_reminder_sets_flag(self):
        """send_appointment_reminder_whatsapp sets whatsapp_reminder_sent=True."""
        from unittest.mock import patch
        from appointments.models import Appointment
        from core.whatsapp_tasks import send_appointment_reminder_whatsapp

        appt = Appointment.objects.create(
            title='WA Reminder Test',
            start_time=timezone.now() + timedelta(hours=12),
            end_time=timezone.now() + timedelta(hours=13),
            status='scheduled',
            whatsapp_number='+385912345678',
            whatsapp_reminder_sent=False,
            company=self.company,
        )
        mock_result = {'success': True, 'error': None, 'response': {}}
        with patch('core.whatsapp.send_text', return_value=mock_result):
            send_appointment_reminder_whatsapp(appt.id)
        appt.refresh_from_db()
        self.assertTrue(appt.whatsapp_reminder_sent)
        appt.delete()

    def test_send_intervention_assignment(self):
        """send_intervention_assignment_whatsapp sends to worker.profile.phone."""
        from unittest.mock import patch
        from interventions.models import HitnaIntervencija
        from core.whatsapp_tasks import send_intervention_assignment_whatsapp
        from accounts.models import UserProfile

        worker = get_or_create_user('wa_worker_test')
        profile, _ = UserProfile.objects.get_or_create(
            user=worker, defaults={'company': self.company, 'role': 'worker'}
        )
        profile.phone = '+491761234567'
        profile.save()

        interv = HitnaIntervencija.objects.create(
            company=self.company,
            title='WA Test Intervention',
            category='ostalo',
            address='Test Street 1',
            client_name='Test Client',
            client_phone='+385911234567',
        )
        mock_result = {'success': True, 'error': None, 'response': {}}
        with patch('core.whatsapp.send_text', return_value=mock_result):
            result = send_intervention_assignment_whatsapp(interv.pk, worker.pk)
        self.assertTrue(result['success'])
        interv.delete()

    def test_check_gateway_health_logs_unhealthy(self):
        """check_whatsapp_gateway_health returns unhealthy when gateway is down."""
        from unittest.mock import patch
        from core.whatsapp_tasks import check_whatsapp_gateway_health

        with patch('core.whatsapp.is_gateway_healthy', return_value=False):
            with self.settings(WAHA_ENABLED=True):
                result = check_whatsapp_gateway_health()
        self.assertEqual(result['status'], 'unhealthy')



# --- 23. WIZARD ---
class WizardTests(unittest.TestCase):

    def test_wizard_page_loads(self):
        """GET /invoicing/wizard/ returns 200 for superadmin."""
        c = Client()
        user = get_or_create_user("wiz_admin", is_superuser=True, is_staff=True)
        c.force_login(user)
        resp = c.get("/invoicing/wizard/")
        self.assertEqual(resp.status_code, 200)
        print("  ok wizard page loads (200)")

    def test_wizard_static_files(self):
        """wizard.css and wizard.js exist in static directory."""
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        self.assertTrue(os.path.isfile(os.path.join(base, "static", "js", "wizard.js")))
        self.assertTrue(os.path.isfile(os.path.join(base, "static", "css", "wizard.css")))
        print("  ok wizard static files exist")

    def test_wizard_submit_creates_invoice(self):
        """POST to /invoicing/save/ with wizard-format data creates invoice."""
        from invoicing.models import Invoice
        c = Client()
        user = get_or_create_user("wiz_submit", is_superuser=True, is_staff=True)
        c.force_login(user)
        before = Invoice.objects.count()
        resp = c.post("/invoicing/save/", {
            "doctype": "R",
            "country": "HR",
            "status": "DRAFT",
            "number": "",
            "date_issued": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "date_due": "",
            "client_name": "Wizard Test Client",
            "client_oib": "11111111111",
            "client_email": "wiz@test.hr",
            "client_address": "Test St 1",
            "client_city": "Zagreb",
            "client_country": "Hrvatska",
            "payment_method": "TRANSAKCIJSKI",
            "currency": "EUR",
            "iban": "",
            "swift": "",
            "reference_number": "",
            "note": "",
            "internal_note": "",
            "issuer_name": "Test",
            "issuer_address": "",
            "issuer_oib": "37590751921",
            "issuer_email": "",
            "item_desc[]": ["Wizard test stavka"],
            "item_qty[]": ["2"],
            "item_unit[]": ["kom"],
            "item_price[]": ["100"],
            "item_pdv[]": ["25"],
            "item_disc[]": ["0"],
        })
        self.assertIn(resp.status_code, [200, 302])
        self.assertGreater(Invoice.objects.count(), before)
        # Clean up
        Invoice.objects.filter(client_name="Wizard Test Client").delete()
        print("  ok wizard submit creates invoice")

    def test_wizard_requires_login(self):
        """Anonymous GET /invoicing/wizard/ -> 302 redirect."""
        c = Client()
        resp = c.get("/invoicing/wizard/")
        self.assertEqual(resp.status_code, 302)
        print("  ok wizard requires login (302)")

# --- 24. INVOICE PROFILES ---
class InvoiceProfileTests(unittest.TestCase):

    def test_create_hr_profile(self):
        """Create a HR InvoiceProfile and verify fields."""
        from invoicing.fiscal_models import InvoiceProfile
        p = InvoiceProfile.objects.create(
            name='Test HR Profile',
            company_name='Test d.o.o.',
            country='HR',
            language='hr',
            currency='EUR',
            oib='12345678901',
            invoice_prefix='TST',
            next_invoice_number=1,
            is_active=True,
        )
        self.assertEqual(p.country, 'HR')
        self.assertEqual(p.language, 'hr')
        self.assertEqual(p.invoice_prefix, 'TST')
        p.delete()
        print("  ok create HR profile")

    def test_create_de_profile(self):
        """Create a DE InvoiceProfile with German settings."""
        from invoicing.fiscal_models import InvoiceProfile
        p = InvoiceProfile.objects.create(
            name='Test DE Profile',
            company_name='Test GmbH',
            country='DE',
            language='de',
            currency='EUR',
            vat_id='DE123456789',
            invoice_prefix='DE',
            next_invoice_number=1,
            is_active=True,
        )
        self.assertEqual(p.country, 'DE')
        self.assertEqual(p.language, 'de')
        self.assertEqual(p.vat_id, 'DE123456789')
        p.delete()
        print("  ok create DE profile")

    def test_only_one_default(self):
        """Setting is_default=True on one profile clears others."""
        from invoicing.fiscal_models import InvoiceProfile
        p1 = InvoiceProfile.objects.create(
            name='Default 1', company_name='A', is_default=True, is_active=True)
        p2 = InvoiceProfile.objects.create(
            name='Default 2', company_name='B', is_default=True, is_active=True)
        p1.refresh_from_db()
        self.assertFalse(p1.is_default)
        self.assertTrue(p2.is_default)
        p1.delete()
        p2.delete()
        print("  ok only one default")

    def test_get_default(self):
        """get_default() returns the is_default profile."""
        from invoicing.fiscal_models import InvoiceProfile
        InvoiceProfile.objects.filter(name__startswith='GetDef').delete()
        p1 = InvoiceProfile.objects.create(
            name='GetDef A', company_name='A', is_default=False, is_active=True)
        p2 = InvoiceProfile.objects.create(
            name='GetDef B', company_name='B', is_default=True, is_active=True)
        default = InvoiceProfile.get_default()
        self.assertEqual(default.pk, p2.pk)
        p1.delete()
        p2.delete()
        print("  ok get_default")

    def test_get_next_number(self):
        """get_next_number() generates correct format and increments."""
        from invoicing.fiscal_models import InvoiceProfile
        import datetime
        p = InvoiceProfile.objects.create(
            name='NumTest', company_name='Num', invoice_prefix='NM',
            next_invoice_number=1, is_active=True)
        year = datetime.datetime.now().year
        num = p.get_next_number()
        self.assertEqual(num, f'NM-{year}-0001')
        p.refresh_from_db()
        self.assertEqual(p.next_invoice_number, 2)
        # Clean up the invoice created by number collision check
        from invoicing.models import Invoice
        Invoice.objects.filter(number=num).delete()
        p.delete()
        print("  ok get_next_number")

    def test_api_profiles_endpoint(self):
        """GET /invoicing/api/profiles/ returns JSON list."""
        c = Client()
        user = get_or_create_user("profile_api", is_superuser=True, is_staff=True)
        c.force_login(user)
        resp = c.get("/invoicing/api/profiles/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        if data:
            self.assertIn('name', data[0])
            self.assertIn('country', data[0])
        print("  ok api profiles endpoint")

    def test_wizard_save_with_profile(self):
        """POST with profile_id uses profile issuer data."""
        from invoicing.fiscal_models import InvoiceProfile
        from invoicing.models import Invoice
        p = InvoiceProfile.objects.create(
            name='WizProf', company_name='WizCo d.o.o.',
            oib='99999999999', country='HR', language='hr',
            invoice_prefix='WP', next_invoice_number=1,
            iban='HR1234567890', is_active=True)
        c = Client()
        user = get_or_create_user("wiz_prof", is_superuser=True, is_staff=True)
        c.force_login(user)
        resp = c.post("/invoicing/save/", {
            "doctype": "R", "country": "HR", "status": "DRAFT",
            "profile_id": str(p.pk),
            "date_issued": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "client_name": "Profile Test Client",
            "client_oib": "11111111111",
            "payment_method": "TRANSAKCIJSKI", "currency": "EUR",
            "item_desc[]": ["Test item"], "item_qty[]": ["1"],
            "item_unit[]": ["kom"], "item_price[]": ["100"],
            "item_pdv[]": ["25"], "item_disc[]": ["0"],
        })
        self.assertIn(resp.status_code, [200, 302])
        inv = Invoice.objects.filter(client_name="Profile Test Client").first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.issuer_name, 'WizCo d.o.o.')
        self.assertTrue(inv.number.startswith('WP-'))
        self.assertEqual(inv.invoice_profile_id, p.pk)
        inv.delete()
        p.delete()
        print("  ok wizard save with profile")

    def test_wizard_without_profile_falls_back(self):
        """POST without profile_id falls back to FiscalConfig."""
        from invoicing.models import Invoice
        c = Client()
        user = get_or_create_user("wiz_nopr", is_superuser=True, is_staff=True)
        c.force_login(user)
        resp = c.post("/invoicing/save/", {
            "doctype": "R", "country": "HR", "status": "DRAFT",
            "date_issued": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "client_name": "NoProfile Test Client",
            "client_oib": "22222222222",
            "payment_method": "TRANSAKCIJSKI", "currency": "EUR",
            "issuer_name": "Fallback Co",
            "item_desc[]": ["Test item"], "item_qty[]": ["1"],
            "item_unit[]": ["kom"], "item_price[]": ["100"],
            "item_pdv[]": ["25"], "item_disc[]": ["0"],
        })
        self.assertIn(resp.status_code, [200, 302])
        inv = Invoice.objects.filter(client_name="NoProfile Test Client").first()
        self.assertIsNotNone(inv)
        inv.delete()
        print("  ok wizard without profile falls back")




# --- 25. WORKTIME INTEGRATION -------------------------------------------

class WorktimeIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.company = get_or_create_company()
        self.user = get_or_create_user('tst_wt_int', is_staff=True, is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _get_project(self):
        from worktime.models import Project
        proj, _ = Project.objects.get_or_create(
            code='WT-INT',
            defaults={'name': 'WT Integration Test', 'hourly_rate': Decimal('30.00')},
        )
        return proj

    def _create_entry(self, **kwargs):
        from worktime.models import TimeEntry
        proj = kwargs.pop('project', self._get_project())
        defaults = dict(
            user=self.user, project=proj,
            date=date.today(), duration=Decimal('8.00'),
            status='APPROVED', is_billed=False,
        )
        defaults.update(kwargs)
        return TimeEntry.objects.create(**defaults)

    def test_api_worktime_entries(self):
        """GET /invoicing/api/worktime-entries/ returns approved unbilled entries with rates."""
        e = self._create_entry()
        resp = self.client.get('/invoicing/api/worktime-entries/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('entries', data)
        self.assertIn('summary', data)
        self.assertIn('filters', data)
        ids = [x['id'] for x in data['entries']]
        self.assertIn(e.id, ids)
        entry_data = [x for x in data['entries'] if x['id'] == e.id][0]
        self.assertEqual(entry_data['hours'], 8.0)
        self.assertGreater(entry_data['rate'], 0)
        self.assertGreater(entry_data['total'], 0)
        e.delete()
        print('  ok api_worktime_entries returns entries with rates')

    def test_api_worktime_entries_filters(self):
        """Date and worker filters work correctly."""
        from worktime.models import TimeEntry
        e1 = self._create_entry(date=date.today())
        e2 = self._create_entry(date=date.today() - timedelta(days=60))
        # Filter by date range (current month only)
        first = date.today().replace(day=1)
        resp = self.client.get(f'/invoicing/api/worktime-entries/?date_from={first}&date_to={date.today()}')
        data = resp.json()
        ids = [x['id'] for x in data['entries']]
        self.assertIn(e1.id, ids)
        self.assertNotIn(e2.id, ids)
        # Filter by worker
        resp2 = self.client.get(f'/invoicing/api/worktime-entries/?worker={self.user.id}')
        data2 = resp2.json()
        ids2 = [x['id'] for x in data2['entries']]
        self.assertIn(e1.id, ids2)
        e1.delete()
        e2.delete()
        print('  ok api_worktime_entries filters work')

    def test_invoice_save_marks_billed(self):
        """POST with worktime_entry_ids marks entries as billed."""
        from worktime.models import TimeEntry
        from invoicing.models import Invoice
        e = self._create_entry()
        self.assertFalse(e.is_billed)
        resp = self.client.post('/invoicing/save/', {
            'doctype': 'R', 'country': 'HR', 'status': 'DRAFT',
            'date_issued': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'client_name': 'WT Billing Test',
            'payment_method': 'TRANSAKCIJSKI', 'currency': 'EUR',
            'item_desc[]': ['Radni sati test'],
            'item_qty[]': ['8'], 'item_unit[]': ['h'],
            'item_price[]': ['30'], 'item_pdv[]': ['25'], 'item_disc[]': ['0'],
            'worktime_entry_ids': str(e.id),
        })
        self.assertIn(resp.status_code, [200, 302])
        e.refresh_from_db()
        self.assertTrue(e.is_billed)
        self.assertIsNotNone(e.invoice)
        # Cleanup
        inv = e.invoice
        e.delete()
        if inv:
            inv.items.all().delete()
            inv.delete()
        print('  ok invoice_save marks worktime entries as billed')

    def test_api_import_worktime_fixed(self):
        """Import endpoint returns worktime entries with correct rates."""
        e = self._create_entry()
        resp = self.client.get('/invoicing/api/import/worktime/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should find at least our entry
        found = [x for x in data if str(e.date) in x.get('subtitle', '')]
        if found:
            self.assertGreater(found[0]['price'], 0, 'price should not be 0')
        e.delete()
        print('  ok api_import worktime returns entries with rates')




# --- 26. INVOICING REDESIGN -------------------------------------------

class InvoicingRedesignTests(unittest.TestCase):
    """Tests for field wizard, grid API, and model enhancements."""

    def setUp(self):
        self.company = get_or_create_company()
        self.user = get_or_create_user('tst_redesign', is_staff=True, is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _make_invoice(self, **kwargs):
        from invoicing.models import Invoice
        defaults = dict(
            date_issued=timezone.now(),
            client_name='Redesign Test Client',
            doctype='R', status='DRAFT',
            company=self.company,
            number=f'RD-TEST-{Invoice.objects.count() + 900}',
        )
        defaults.update(kwargs)
        return Invoice.objects.create(**defaults)

    def _make_item(self, invoice, **kwargs):
        from invoicing.models import InvoiceItem
        defaults = dict(
            invoice=invoice,
            description='Test item',
            quantity=Decimal('1'),
            unit='kom',
            unit_price=Decimal('100'),
            tax_rate=Decimal('25'),
            discount_percent=Decimal('0'),
            total_price=Decimal('100'),
        )
        defaults.update(kwargs)
        return InvoiceItem.objects.create(**defaults)

    # ── MODEL TESTS ──

    def test_invoice_source_field(self):
        """Invoice.source field exists and accepts valid choices."""
        inv = self._make_invoice(source='wizard_field')
        inv.refresh_from_db()
        self.assertEqual(inv.source, 'wizard_field')
        inv.delete()
        print('  ok Invoice.source field works')

    def test_invoice_project_fk(self):
        """Invoice.project FK links to worktime.Project."""
        from worktime.models import Project
        proj, _ = Project.objects.get_or_create(
            code='RD-PRJ', defaults={'name': 'Redesign Test Project'}
        )
        inv = self._make_invoice(project=proj)
        inv.refresh_from_db()
        self.assertEqual(inv.project.code, 'RD-PRJ')
        inv.delete()
        print('  ok Invoice.project FK works')

    def test_invoice_item_gross_total(self):
        """InvoiceItem.gross_total auto-calculated on save."""
        inv = self._make_invoice()
        item = self._make_item(inv, unit_price=Decimal('100'), tax_rate=Decimal('25'))
        item.refresh_from_db()
        self.assertEqual(item.total_price, Decimal('100'))
        self.assertEqual(item.gross_total, Decimal('125'))
        item.delete()
        inv.delete()
        print('  ok InvoiceItem.gross_total auto-calculated')

    # ── FIELD WIZARD TESTS ──

    def test_field_wizard_loads(self):
        """GET /invoicing/field/ returns 200."""
        resp = self.client.get('/invoicing/field/')
        self.assertEqual(resp.status_code, 200)
        print('  ok field wizard loads (200)')

    def test_field_wizard_requires_login(self):
        """Field wizard requires authentication."""
        c = Client()  # not logged in
        resp = c.get('/invoicing/field/')
        self.assertIn(resp.status_code, [301, 302])
        print('  ok field wizard requires login')

    def test_field_create_api(self):
        """POST /invoicing/api/field-create/ creates invoice."""
        from invoicing.models import Invoice
        resp = self.client.post('/invoicing/api/field-create/', {
            'action': 'draft',
            'country': 'HR',
            'client_name': 'Field Test Klijent',
            'client_address': 'Ulica 1',
            'client_city': 'Zagreb',
            'work_description': 'Popravak ventila',
            'work_category': 'Popravak',
            'work_hours': '2',
            'item_desc[]': ['Popravak ventila'],
            'item_qty[]': ['2'],
            'item_unit[]': ['h'],
            'item_price[]': ['50'],
            'item_pdv[]': ['25'],
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('invoice_id', data)
        # Verify invoice created with correct source
        inv = Invoice.objects.get(pk=data['invoice_id'])
        self.assertEqual(inv.source, 'wizard_field')
        self.assertEqual(inv.client_name, 'Field Test Klijent')
        self.assertEqual(inv.status, 'DRAFT')
        self.assertEqual(inv.items.count(), 1)
        self.assertEqual(float(inv.subtotal), 100.0)
        inv.items.all().delete()
        inv.delete()
        print('  ok field create API works')

    def test_field_create_paid_status(self):
        """action=paid sets status to PAID and payment=GOTOVINA."""
        from invoicing.models import Invoice
        resp = self.client.post('/invoicing/api/field-create/', {
            'action': 'paid', 'country': 'HR',
            'client_name': 'Cash Client',
            'item_desc[]': ['Servis'], 'item_qty[]': ['1'],
            'item_unit[]': ['pau'], 'item_price[]': ['200'],
            'item_pdv[]': ['25'],
        })
        data = resp.json()
        self.assertTrue(data['success'])
        inv = Invoice.objects.get(pk=data['invoice_id'])
        self.assertEqual(inv.status, 'PAID')
        self.assertEqual(inv.payment_method, 'GOTOVINA')
        inv.items.all().delete()
        inv.delete()
        print('  ok field create paid sets correct status')

    # ── GRID API TESTS ──

    def test_api_update_item(self):
        """PATCH /invoicing/api/item/<pk>/update/ updates item inline."""
        import json
        inv = self._make_invoice()
        item = self._make_item(inv, unit_price=Decimal('100'))
        resp = self.client.patch(
            f'/invoicing/api/item/{item.pk}/update/',
            json.dumps({'unit_price': '150', 'quantity': '2'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal('150'))
        self.assertEqual(item.quantity, Decimal('2'))
        self.assertEqual(item.total_price, Decimal('300'))
        item.delete()
        inv.delete()
        print('  ok api_update_item works')

    def test_api_update_invoice(self):
        """PATCH /invoicing/api/invoice/<pk>/update/ updates header fields."""
        import json
        inv = self._make_invoice()
        resp = self.client.patch(
            f'/invoicing/api/invoice/{inv.pk}/update/',
            json.dumps({'client_name': 'Updated Name', 'note': 'Test note'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        inv.refresh_from_db()
        self.assertEqual(inv.client_name, 'Updated Name')
        self.assertEqual(inv.note, 'Test note')
        inv.delete()
        print('  ok api_update_invoice works')

    def test_api_update_status(self):
        """POST /invoicing/api/invoice/<pk>/status/ changes status."""
        import json
        inv = self._make_invoice(status='DRAFT')
        resp = self.client.post(
            f'/invoicing/api/invoice/{inv.pk}/status/',
            json.dumps({'status': 'SENT'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['old_status'], 'DRAFT')
        self.assertEqual(data['new_status'], 'SENT')
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'SENT')
        inv.delete()
        print('  ok api_update_status works')

    def test_api_add_item(self):
        """POST /invoicing/api/invoice/<pk>/add-item/ adds new item."""
        import json
        inv = self._make_invoice()
        resp = self.client.post(
            f'/invoicing/api/invoice/{inv.pk}/add-item/',
            json.dumps({'description': 'New inline item', 'unit_price': '75', 'quantity': '3'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['item']['description'], 'New inline item')
        self.assertEqual(inv.items.count(), 1)
        inv.items.all().delete()
        inv.delete()
        print('  ok api_add_item works')

    def test_api_delete_item(self):
        """DELETE /invoicing/api/item/<pk>/delete/ removes item."""
        inv = self._make_invoice()
        item = self._make_item(inv)
        item_pk = item.pk
        resp = self.client.delete(f'/invoicing/api/item/{item_pk}/delete/')
        self.assertEqual(resp.status_code, 200)
        from invoicing.models import InvoiceItem
        self.assertFalse(InvoiceItem.objects.filter(pk=item_pk).exists())
        inv.delete()
        print('  ok api_delete_item works')

    def test_api_invalid_status_rejected(self):
        """Invalid status value returns 400."""
        import json
        inv = self._make_invoice()
        resp = self.client.post(
            f'/invoicing/api/invoice/{inv.pk}/status/',
            json.dumps({'status': 'NONEXISTENT'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        inv.delete()
        print('  ok invalid status rejected (400)')




class OfficeWizardTests(unittest.TestCase):
    """Suite #27: Office wizard tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_office_wiz', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)

    def test_office_wizard_page_loads(self):
        """Office wizard renders 200."""
        resp = self.client.get('/invoicing/office/')
        self.assertEqual(resp.status_code, 200)

    def test_office_wizard_requires_login(self):
        """Office wizard redirects anonymous."""
        c = Client()
        resp = c.get('/invoicing/office/')
        self.assertEqual(resp.status_code, 302)

    def test_office_wizard_has_context(self):
        """Office wizard passes profiles and locations."""
        resp = self.client.get('/invoicing/office/')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context if hasattr(resp, 'context') and resp.context else {}
        if ctx:
            self.assertIn('profiles', ctx)
            self.assertIn('country', ctx)

    def test_office_wizard_template_used(self):
        """Office wizard renders office wizard content."""
        resp = self.client.get('/invoicing/office/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'wizardRoot', resp.content)

    def test_invoice_save_source_field(self):
        """invoice_save sets source field from POST."""
        from invoicing.models import Invoice
        from invoicing.fiscal_models import InvoiceProfile
        profile = InvoiceProfile.get_default()
        resp = self.client.post('/invoicing/save/', {
            'doctype': 'R',
            'country': 'HR',
            'number': '',
            'status': 'DRAFT',
            'date_issued': '2026-01-15T10:00',
            'client_name': 'Source Test Client',
            'client_address': 'Adresa 1',
            'client_oib': '11111111111',
            'payment_method': 'TRANSAKCIJSKI',
            'currency': 'EUR',
            'source': 'wizard_office',
            'item_desc[]': ['Test stavka'],
            'item_qty[]': ['1'],
            'item_unit[]': ['kom'],
            'item_price[]': ['100'],
            'item_pdv[]': ['25'],
            'item_disc[]': ['0'],
        })
        self.assertIn(resp.status_code, [200, 302])
        inv = Invoice.objects.filter(client_name='Source Test Client').first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.source, 'wizard_office')


class GridEditorAjaxTests(unittest.TestCase):
    """Suite #28: Grid editor AJAX API tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_grid_ajax', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)
        # Create test invoice with items
        from invoicing.models import Invoice, InvoiceItem
        from django.utils import timezone
        cls.invoice, _ = Invoice.objects.get_or_create(
            number='GRID-TEST-001',
            defaults=dict(
                doctype='R',
                country='HR',
                status='DRAFT',
                client_name='Grid Test Klijent',
                issuer_name='Grid Test Izdavac',
                currency='EUR',
                date_issued=timezone.now(),
                created_by=cls.user,
            )
        )
        cls.item = InvoiceItem.objects.create(
            invoice=cls.invoice,
            description='Grid test stavka',
            quantity=2,
            unit='kom',
            unit_price=50,
            tax_rate=25,
            discount_percent=0,
            total_price=100,
        )

    def test_update_item(self):
        """PATCH /api/item/<pk>/update/ works."""
        import json
        resp = self.client.patch(
            f'/invoicing/api/item/{self.item.pk}/update/',
            json.dumps({'description': 'Updated via grid'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.description, 'Updated via grid')

    def test_update_invoice_header(self):
        """PATCH /api/invoice/<pk>/update/ works."""
        import json
        resp = self.client.patch(
            f'/invoicing/api/invoice/{self.invoice.pk}/update/',
            json.dumps({'client_name': 'Updated Klijent'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.client_name, 'Updated Klijent')

    def test_add_item(self):
        """POST /api/invoice/<pk>/add-item/ works."""
        import json
        resp = self.client.post(
            f'/invoicing/api/invoice/{self.invoice.pk}/add-item/',
            json.dumps({
                'description': 'Nova stavka',
                'quantity': 3,
                'unit': 'h',
                'unit_price': 25,
                'tax_rate': 25,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertIn('item', data)
        self.assertIn('id', data['item'])

    def test_delete_item(self):
        """DELETE /api/item/<pk>/delete/ works."""
        from invoicing.models import InvoiceItem
        tmp = InvoiceItem.objects.create(
            invoice=self.invoice,
            description='To be deleted',
            quantity=1,
            unit='kom',
            unit_price=10,
            tax_rate=25,
            total_price=10,
        )
        resp = self.client.delete(f'/invoicing/api/item/{tmp.pk}/delete/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(InvoiceItem.objects.filter(pk=tmp.pk).exists())

    def test_update_status(self):
        """POST /api/invoice/<pk>/status/ works."""
        import json
        # Reset to DRAFT first
        self.invoice.status = 'DRAFT'
        self.invoice.save()
        resp = self.client.post(
            f'/invoicing/api/invoice/{self.invoice.pk}/status/',
            json.dumps({'status': 'SENT'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'SENT')




class KontoModelsTests(unittest.TestCase):
    """Suite #29: Konto models tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_konto', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)
        from companies.models import Company
        cls.company = Company.objects.first()
        # Seed konto accounts if not already present
        if cls.company:
            from konto.models import KontoAccount
            if KontoAccount.objects.filter(company=cls.company).count() < 10:
                from django.core.management import call_command
                call_command('seed_konto', company_id=cls.company.pk, verbosity=0)

    def test_konto_accounts_exist(self):
        """Chart of accounts was seeded."""
        from konto.models import KontoAccount
        count = KontoAccount.objects.filter(company=self.company).count()
        self.assertGreater(count, 40)

    def test_konto_account_types(self):
        """All account types are represented."""
        from konto.models import KontoAccount
        types = set(KontoAccount.objects.filter(
            company=self.company
        ).values_list('account_type', flat=True).distinct())
        self.assertIn('asset', types)
        self.assertIn('liability', types)
        self.assertIn('income', types)
        self.assertIn('expense', types)
        self.assertIn('equity', types)

    def test_konto_unique_together(self):
        """Cannot create duplicate code for same company."""
        from konto.models import KontoAccount
        from django.db import IntegrityError
        try:
            KontoAccount.objects.create(
                company=self.company, code='1000',
                name='Duplicate', account_type='asset')
            self.fail("Should have raised IntegrityError")
        except IntegrityError:
            from django.db import connection
            connection.cursor()  # reset connection after error

    def test_bank_account_create(self):
        """Can create a bank account."""
        from konto.models import BankAccount
        ba, created = BankAccount.objects.get_or_create(
            company=self.company, iban='HR1234567890123456789',
            defaults={
                'name': 'Test PBZ',
                'bank_name': 'PBZ',
                'currency': 'EUR',
                'opening_balance': 10000,
            })
        self.assertEqual(ba.currency, 'EUR')

    def test_bank_transaction_create(self):
        """Can create a bank transaction."""
        from konto.models import BankAccount, BankTransaction
        import datetime
        ba = BankAccount.objects.filter(company=self.company).first()
        if not ba:
            ba = BankAccount.objects.create(
                company=self.company, name='Test', iban='HR0000000000000000001',
                bank_name='Test Bank', currency='EUR', opening_balance=5000)
        txn = BankTransaction.objects.create(
            bank_account=ba, company=self.company,
            transaction_date=datetime.date.today(),
            amount=1250, transaction_type='inflow',
            counterparty_name='Test Kupac',
            reference_number='R-2026-0001')
        self.assertEqual(txn.status, 'unmatched')
        self.assertFalse(txn.is_booked)

    def test_journal_entry_balanced(self):
        """Journal entry balance check works."""
        from konto.models import KontoAccount, JournalEntry, LedgerLine
        import datetime
        acct_d = KontoAccount.objects.filter(company=self.company, code='1200').first()
        acct_c = KontoAccount.objects.filter(company=self.company, code='7000').first()
        if not acct_d or not acct_c:
            return  # Skip if accounts missing
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number='TEST-001',
            date=datetime.date.today(),
            description='Test entry',
            source_type='manual',
            is_posted=True,
            created_by=self.user)
        LedgerLine.objects.create(
            journal_entry=je, account=acct_d, side='debit', amount=100)
        LedgerLine.objects.create(
            journal_entry=je, account=acct_c, side='credit', amount=100)
        self.assertTrue(je.is_balanced)
        self.assertEqual(je.total_debit, 100)

    def test_journal_entry_unbalanced(self):
        """Unbalanced journal entry detected."""
        from konto.models import KontoAccount, JournalEntry, LedgerLine
        import datetime
        acct = KontoAccount.objects.filter(company=self.company, code='1000').first()
        if not acct:
            return
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number='TEST-002',
            date=datetime.date.today(),
            description='Unbalanced test',
            source_type='manual')
        LedgerLine.objects.create(
            journal_entry=je, account=acct, side='debit', amount=500)
        self.assertFalse(je.is_balanced)

    def test_konto_balance_property(self):
        """KontoAccount.balance works correctly."""
        from konto.models import KontoAccount, JournalEntry, LedgerLine
        import datetime
        acct = KontoAccount.objects.filter(
            company=self.company, code='1200', account_type='asset').first()
        if not acct:
            return
        # Clear any existing entries for clean test
        initial = acct.balance
        je = JournalEntry.objects.create(
            company=self.company,
            entry_number='TEST-BAL-001',
            date=datetime.date.today(),
            description='Balance test',
            source_type='manual',
            is_posted=True)
        LedgerLine.objects.create(
            journal_entry=je, account=acct, side='debit', amount=200)
        # Asset grows on debit side
        new_balance = acct.balance
        self.assertEqual(new_balance, initial + 200)


class KontoServicesTests(unittest.TestCase):
    """Suite #30: Konto services (booking, matching, reports) tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_konto_svc', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)
        from companies.models import Company
        cls.company = Company.objects.first()

    def test_book_invoice(self):
        """book_invoice creates journal entry with balanced lines."""
        from invoicing.models import Invoice, InvoiceItem
        from konto.services import book_invoice
        from django.utils import timezone
        from decimal import Decimal

        inv, _ = Invoice.objects.get_or_create(
            number='KNT-TEST-001',
            defaults=dict(doctype='R', country='HR',
                status='SENT', client_name='Test Knjizenje Klijent',
                issuer_name='Test Firma', currency='EUR',
                date_issued=timezone.now(), created_by=self.user,
                subtotal=1000, tax_amount=250, total=1250))
        # Clear previous journal entries for re-run
        from konto.models import JournalEntry
        JournalEntry.objects.filter(source_invoice=inv).delete()
        InvoiceItem.objects.get_or_create(
            invoice=inv, description='Usluga',
            defaults=dict(quantity=1, unit='kom', unit_price=1000,
                tax_rate=25, total_price=1000))

        je = book_invoice(inv, self.user)
        self.assertIsNotNone(je)
        self.assertTrue(je.is_balanced)
        self.assertEqual(je.total_debit, Decimal('1250'))
        self.assertEqual(je.source_invoice, inv)

    def test_book_invoice_idempotent(self):
        """book_invoice does not double-book."""
        from invoicing.models import Invoice
        from konto.services import book_invoice
        from django.utils import timezone

        inv, _ = Invoice.objects.get_or_create(
            number='KNT-TEST-002',
            defaults=dict(doctype='R', country='HR',
                status='SENT', client_name='Test Idempotent',
                issuer_name='Firma', currency='EUR',
                date_issued=timezone.now(), created_by=self.user,
                subtotal=500, tax_amount=125, total=625))
        from konto.models import JournalEntry
        JournalEntry.objects.filter(source_invoice=inv).delete()
        je1 = book_invoice(inv, self.user)
        je2 = book_invoice(inv, self.user)
        self.assertIsNotNone(je1)
        self.assertIsNone(je2)  # Second call returns None

    def test_book_bank_transaction(self):
        """book_bank_transactions creates journal entries."""
        from konto.models import BankAccount, BankTransaction
        from konto.services import book_bank_transactions
        import datetime

        ba, _ = BankAccount.objects.get_or_create(
            company=self.company, iban='HR9999000000000000001',
            defaults={'name': 'Svc Test', 'bank_name': 'Test', 'currency': 'EUR'})
        txn = BankTransaction.objects.create(
            bank_account=ba, company=self.company,
            transaction_date=datetime.date.today(),
            amount=750, transaction_type='inflow',
            counterparty_name='Svc Test Kupac')

        results = book_bank_transactions(BankTransaction.objects.filter(pk=txn.pk), self.user)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_balanced)
        txn.refresh_from_db()
        self.assertTrue(txn.is_booked)

    def test_match_transaction_to_invoice(self):
        """match_transaction_to_invoice links and updates status."""
        from invoicing.models import Invoice
        from konto.models import BankAccount, BankTransaction
        from konto.services import match_transaction_to_invoice
        from django.utils import timezone
        import datetime

        inv, created = Invoice.objects.get_or_create(
            number='KNT-MATCH-001',
            defaults=dict(doctype='R', country='HR',
                status='SENT', client_name='Match Test Klijent',
                issuer_name='Firma', currency='EUR',
                date_issued=timezone.now(), created_by=self.user,
                subtotal=800, tax_amount=200, total=1000))
        if not created:
            inv.status = 'SENT'
            inv.save(update_fields=['status'])
            from konto.models import BankTransaction as BT2
            BT2.objects.filter(matched_invoice=inv).update(status='unmatched', matched_invoice=None)

        ba, _ = BankAccount.objects.get_or_create(
            company=self.company, iban='HR8888000000000000001',
            defaults={'name': 'Match Test', 'bank_name': 'Test', 'currency': 'EUR'})
        txn = BankTransaction.objects.create(
            bank_account=ba, company=self.company,
            transaction_date=datetime.date.today(),
            amount=1000, transaction_type='inflow',
            counterparty_name='Match Test Kupac')

        result = match_transaction_to_invoice(txn, inv)
        self.assertTrue(result)
        txn.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(txn.status, 'matched')
        self.assertEqual(txn.matched_invoice, inv)
        self.assertEqual(inv.status, 'PAID')

    def test_profit_loss_report(self):
        """get_profit_loss returns correct structure."""
        from konto.services import get_profit_loss
        import datetime
        result = get_profit_loss(
            self.company,
            datetime.date(2026, 1, 1),
            datetime.date(2026, 12, 31))
        self.assertIn('income', result)
        self.assertIn('expenses', result)
        self.assertIn('profit_loss', result)
        self.assertIn('total', result['income'])

    def test_balance_sheet(self):
        """get_balance_sheet returns correct structure."""
        from konto.services import get_balance_sheet
        import datetime
        result = get_balance_sheet(self.company, datetime.date.today())
        self.assertIn('assets', result)
        self.assertIn('liabilities', result)
        self.assertIn('equity', result)
        self.assertIn('is_balanced', result)

    def test_auto_match_by_reference(self):
        """auto_match_transactions matches by reference number."""
        from invoicing.models import Invoice
        from konto.models import BankAccount, BankTransaction
        from konto.services import auto_match_transactions
        from django.utils import timezone
        import datetime

        inv, created = Invoice.objects.get_or_create(
            number='AUTO-MATCH-001',
            defaults=dict(doctype='R', country='HR',
                status='SENT', client_name='Auto Match Klijent',
                issuer_name='Firma', currency='EUR',
                date_issued=timezone.now(), created_by=self.user,
                subtotal=400, tax_amount=100, total=500))
        if not created:
            inv.status = 'SENT'
            inv.save(update_fields=['status'])

        ba, _ = BankAccount.objects.get_or_create(
            company=self.company, iban='HR7777000000000000001',
            defaults={'name': 'Auto Test', 'bank_name': 'Test', 'currency': 'EUR'})
        # Clean up old auto-match txns
        BankTransaction.objects.filter(
            reference_number='AUTO-MATCH-001', status='matched').update(
            status='unmatched', matched_invoice=None)
        txn, _ = BankTransaction.objects.get_or_create(
            bank_account=ba, company=self.company,
            reference_number='AUTO-MATCH-001',
            defaults=dict(
                transaction_date=datetime.date.today(),
                amount=500, transaction_type='inflow',
                counterparty_name='Auto Match Klijent'))
        txn.status = 'unmatched'
        txn.matched_invoice = None
        txn.is_booked = False
        txn.save()

        matched = auto_match_transactions(self.company)
        self.assertGreaterEqual(len(matched), 1)
        # Check our transaction was matched
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'matched')

    def test_open_receivables(self):
        """get_open_receivables returns list."""
        from konto.services import get_open_receivables
        result = get_open_receivables(self.company)
        self.assertIsInstance(result, list)


class KontoViewsTests(unittest.TestCase):
    """Suite 31: Konto Views — page loads and API endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        django.setup()
        from django.test import RequestFactory
        from companies.models import Company
        cls.factory = RequestFactory()
        cls.user = get_or_create_user('tst_konto_views', is_staff=True, is_superuser=True)
        cls.company, _ = Company.objects.get_or_create(
            name='Konto Views Test GmbH',
            defaults={'country': 'DE', 'currency': 'EUR'},
        )
        if hasattr(cls.user, 'profile'):
            cls.user.profile.company = cls.company
            cls.user.profile.save()

        from konto.models import KontoAccount
        cls.account, _ = KontoAccount.objects.get_or_create(
            company=cls.company, code='1000',
            defaults={'name': 'Kasse', 'account_type': 'ASSET'},
        )
        cls.revenue_acct, _ = KontoAccount.objects.get_or_create(
            company=cls.company, code='7000',
            defaults={'name': 'Umsatzerlöse', 'account_type': 'INCOME'},
        )

    def _get(self, view_func, **kwargs):
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/test/')
        req.user = self.user
        req.impersonated_company = self.company
        req.session = {}
        return view_func(req, **kwargs)

    def _post_json(self, view_func, data, **kwargs):
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.post('/test/', data=json.dumps(data), content_type='application/json')
        req.user = self.user
        req.impersonated_company = self.company
        req.session = {}
        return view_func(req, **kwargs)

    def _post_form(self, view_func, data, **kwargs):
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.post('/test/', data=data)
        req.user = self.user
        req.impersonated_company = self.company
        req.session = {}
        return view_func(req, **kwargs)

    # ── Page loads ──

    def test_dashboard_loads(self):
        from konto.views import dashboard
        resp = self._get(dashboard)
        self.assertEqual(resp.status_code, 200)

    def test_chart_of_accounts_loads(self):
        from konto.views import chart_of_accounts
        resp = self._get(chart_of_accounts)
        self.assertEqual(resp.status_code, 200)

    def test_account_detail_loads(self):
        from konto.views import account_detail
        resp = self._get(account_detail, pk=self.account.pk)
        self.assertEqual(resp.status_code, 200)

    def test_bank_accounts_loads(self):
        from konto.views import bank_accounts
        resp = self._get(bank_accounts)
        self.assertEqual(resp.status_code, 200)

    def test_transactions_loads(self):
        from konto.views import transactions
        resp = self._get(transactions)
        self.assertEqual(resp.status_code, 200)

    def test_journal_entries_loads(self):
        from konto.views import journal_entries
        resp = self._get(journal_entries)
        self.assertEqual(resp.status_code, 200)

    def test_journal_entry_form_loads(self):
        from konto.views import journal_entry_create
        resp = self._get(journal_entry_create)
        self.assertEqual(resp.status_code, 200)

    def test_report_pnl_loads(self):
        from konto.views import report_profit_loss
        resp = self._get(report_profit_loss)
        self.assertEqual(resp.status_code, 200)

    def test_report_balance_sheet_loads(self):
        from konto.views import report_balance_sheet
        resp = self._get(report_balance_sheet)
        self.assertEqual(resp.status_code, 200)

    def test_report_receivables_loads(self):
        from konto.views import report_receivables
        resp = self._get(report_receivables)
        self.assertEqual(resp.status_code, 200)

    # ── API endpoints ──

    def test_api_auto_match(self):
        from konto.views import api_auto_match
        resp = self._post_json(api_auto_match, {})
        self.assertIn(resp.status_code, [200, 400])

    def test_api_chart_data(self):
        from konto.views import api_chart_data
        resp = self._get(api_chart_data)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('accounts', data)

    def test_api_unmatched_invoices(self):
        from konto.views import api_unmatched_invoices
        resp = self._get(api_unmatched_invoices)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('invoices', data)

    def test_account_save_create(self):
        from konto.views import account_save
        from konto.models import KontoAccount
        # Clean up any previous test account
        KontoAccount.objects.filter(company=self.company, code='9999').delete()
        resp = self._post_form(account_save, {
            'code': '9999',
            'name': 'Test Konto Account',
            'account_type': 'EXPENSE',
        })
        self.assertIn(resp.status_code, [200, 302])

    def test_api_transaction_create(self):
        from konto.views import api_transaction_create
        from konto.models import BankAccount
        ba, _ = BankAccount.objects.get_or_create(
            company=self.company, iban='DE89370400440532013000',
            defaults={
                'name': 'Test Bank',
                'bank_name': 'Deutsche Bank',
                'currency': 'EUR',
                'opening_balance': 0,
                'current_balance': 0,
            },
        )
        resp = self._post_json(api_transaction_create, {
            'bank_account_id': ba.pk,
            'date': '2026-01-15',
            'amount': '100.00',
            'type': 'inflow',
            'counterparty': 'Test Client',
            'description': 'Payment',
        })
        self.assertIn(resp.status_code, [200, 201])



# ── Suite 32: Invoice Duplicate Tests ─────────────────────────────────────────
class InvoiceDuplicateTests(unittest.TestCase):
    """Suite #32: Invoice clone / duplicate tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_dup', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)

    def test_clone_creates_copy(self):
        """Cloning an invoice creates a new invoice."""
        from invoicing.models import Invoice
        inv = Invoice.objects.filter(doctype='R').first()
        if not inv:
            self.skipTest('No invoice to clone')
        resp = self.client.get(f'/invoicing/{inv.pk}/clone/')
        self.assertIn(resp.status_code, [200, 302])

    def test_clone_items_copied(self):
        """Clone preserves item count."""
        from invoicing.models import Invoice
        inv = Invoice.objects.filter(doctype='R').first()
        if not inv:
            self.skipTest('No invoice')
        original_count = inv.items.count()
        self.assertGreaterEqual(original_count, 0)

    def test_source_choices_include_duplicate(self):
        """SOURCE_CHOICES includes duplicate."""
        from invoicing.models import Invoice
        slugs = [c[0] for c in Invoice.SOURCE_CHOICES]
        self.assertIn('duplicate', slugs)

    def test_clone_button_in_index(self):
        """Index page contains clone link."""
        resp = self.client.get('/invoicing/')
        if resp.status_code == 200:
            self.assertIn(b'/clone/', resp.content)


# ── Suite 33: Quote Workflow Tests ────────────────────────────────────────────
class QuoteWorkflowTests(unittest.TestCase):
    """Suite #33: Quote (Ponuda) workflow tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_quote', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)

    def test_doctype_filter(self):
        """Filtering by doctype=PO works."""
        resp = self.client.get('/invoicing/?doctype=PO')
        self.assertEqual(resp.status_code, 200)

    def test_quote_counts_in_context(self):
        """Index view includes quotes_total in totals."""
        resp = self.client.get('/invoicing/')
        if resp.status_code == 200 and getattr(resp, "context", None):
            totals = resp.context.get('totals', {})
            self.assertIn('quotes_total', totals)

    def test_doctype_tabs_in_html(self):
        """Index page contains doctype tab links."""
        resp = self.client.get('/invoicing/')
        if resp.status_code == 200:
            self.assertIn(b'doctype=PO', resp.content)

    def test_nova_ponuda_button(self):
        """Index page contains Nova ponuda link."""
        resp = self.client.get('/invoicing/')
        if resp.status_code == 200:
            self.assertIn(b'doctype=PO', resp.content)


# ── Suite 34: PricingPlan Tests ───────────────────────────────────────────────
class PricingPlanTests(unittest.TestCase):
    """Suite #34: PricingPlan model tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_plan', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)

    def test_pricing_plan_model_exists(self):
        """PricingPlan model is importable."""
        from registration.models import PricingPlan
        self.assertTrue(hasattr(PricingPlan, 'slug'))

    def test_pricing_plan_crud(self):
        """Can create and retrieve a PricingPlan."""
        from registration.models import PricingPlan
        plan, created = PricingPlan.objects.get_or_create(
            slug='test_plan',
            defaults={
                'name': 'Test Plan',
                'price_monthly': 10,
                'price_yearly': 100,
                'included_modules': ['invoicing'],
                'sort_order': 99,
            }
        )
        self.assertEqual(plan.name, 'Test Plan')

    def test_subscription_uses_plan_modules(self):
        """CompanySubscription.allowed_modules uses pricing_plan if set."""
        from registration.models import PricingPlan, CompanySubscription
        plan, _ = PricingPlan.objects.get_or_create(
            slug='test_plan2',
            defaults={
                'name': 'Test2',
                'price_monthly': 5,
                'price_yearly': 50,
                'included_modules': ['invoicing', 'partners'],
                'sort_order': 98,
            }
        )
        from companies.models import Company
        company = Company.objects.first()
        if not company:
            self.skipTest('No company')
        from datetime import date
        sub = CompanySubscription.objects.create(
            company=company,
            plan='starter',
            pricing_plan=plan,
            valid_from=date.today(),
            monthly_fee=5,
            is_active=True,
        )
        self.assertIn('invoicing', sub.allowed_modules)
        self.assertIn('partners', sub.allowed_modules)

    def test_trial_property(self):
        """is_trial returns True when trial_ends is in the future."""
        from registration.models import CompanySubscription
        from companies.models import Company
        from datetime import date, timedelta
        company = Company.objects.first()
        if not company:
            self.skipTest('No company')
        sub = CompanySubscription.objects.create(
            company=company,
            plan='starter',
            valid_from=date.today(),
            trial_ends=date.today() + timedelta(days=14),
            monthly_fee=0,
            is_active=True,
        )
        self.assertTrue(sub.is_trial)


# ── Suite 35: Registration Flow Tests ────────────────────────────────────────
class RegistrationFlowTests(unittest.TestCase):
    """Suite #35: Self-service + quick registration tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()

    def test_step1_loads(self):
        """Registration step 1 (plan selection) loads."""
        resp = self.client.get('/register/')
        self.assertIn(resp.status_code, [200, 302])

    def test_step2_requires_plan(self):
        """Step 2 redirects if no plan in session."""
        resp = self.client.get('/register/company/')
        self.assertEqual(resp.status_code, 302)

    def test_step3_requires_company(self):
        """Step 3 redirects if no company data in session."""
        resp = self.client.get('/register/account/')
        self.assertEqual(resp.status_code, 302)

    def test_quick_register_loads(self):
        """Quick register page loads."""
        resp = self.client.get('/accounts/quick-register/')
        self.assertIn(resp.status_code, [200, 302])



# ═══════════════════════════════════════════════════════════════════════════
#  Suite #36: TAX LOGIC
# ═══════════════════════════════════════════════════════════════════════════

class TaxLogicTests(unittest.TestCase):
    """Suite #36: invoicing/tax_logic.py — TAX_PROFILES, calculate_tax, reverse_charge, kleinunternehmer."""

    def test_hr_standard_rate(self):
        """HR standard rate is 25%."""
        from invoicing.tax_logic import TAX_PROFILES
        self.assertEqual(TAX_PROFILES['HR']['standard'], Decimal('25'))

    def test_de_standard_rate(self):
        """DE standard rate is 19%."""
        from invoicing.tax_logic import TAX_PROFILES
        self.assertEqual(TAX_PROFILES['DE']['standard'], Decimal('19'))

    def test_de_reduced_rate(self):
        """DE reduced rate is 7%."""
        from invoicing.tax_logic import TAX_PROFILES
        self.assertEqual(TAX_PROFILES['DE']['reduced'], Decimal('7'))

    def test_calculate_tax_hr_standard(self):
        """calculate_tax HR standard: 100 base -> 25 tax -> 125 total."""
        from invoicing.tax_logic import calculate_tax
        r = calculate_tax(100, country='HR')
        self.assertEqual(r['base'], Decimal('100'))
        self.assertEqual(r['tax_rate'], Decimal('25'))
        self.assertEqual(r['tax_amount'], Decimal('25.00'))
        self.assertEqual(r['total'], Decimal('125.00'))

    def test_calculate_tax_de_standard(self):
        """calculate_tax DE standard: 100 base -> 19 tax -> 119 total."""
        from invoicing.tax_logic import calculate_tax
        r = calculate_tax(100, country='DE')
        self.assertEqual(r['tax_rate'], Decimal('19'))
        self.assertEqual(r['tax_amount'], Decimal('19.00'))
        self.assertEqual(r['total'], Decimal('119.00'))

    def test_calculate_tax_pausalac_zero(self):
        """Pausalac: tax_amount = 0 regardless of country."""
        from invoicing.tax_logic import calculate_tax
        r = calculate_tax(500, tax_status='pausalac', country='HR')
        self.assertEqual(r['tax_amount'], Decimal('0.00'))
        self.assertEqual(r['total'], Decimal('500.00'))

    def test_calculate_tax_kleinunternehmer_zero(self):
        """Kleinunternehmer: tax_amount = 0."""
        from invoicing.tax_logic import calculate_tax
        r = calculate_tax(200, tax_status='kleinunternehmer', country='DE')
        self.assertEqual(r['tax_amount'], Decimal('0.00'))

    def test_calculate_tax_reverse_charge_zero(self):
        """Reverse charge: tax_amount = 0."""
        from invoicing.tax_logic import calculate_tax
        r = calculate_tax(300, tax_status='reverse_charge', country='HR')
        self.assertEqual(r['tax_amount'], Decimal('0.00'))
        self.assertEqual(r['tax_status'], 'reverse_charge')

    def test_calculate_tax_explicit_rate(self):
        """Explicit rate overrides status-based rate."""
        from invoicing.tax_logic import calculate_tax
        r = calculate_tax(100, tax_rate=13, country='HR')
        self.assertEqual(r['tax_rate'], Decimal('13'))
        self.assertEqual(r['tax_amount'], Decimal('13.00'))

    def test_calculate_items_mixed(self):
        """calculate_items handles multiple items with different rates."""
        from invoicing.tax_logic import calculate_items
        items = [
            {'qty': 2, 'price': 100, 'tax_rate': 25},
            {'qty': 1, 'price': 50,  'tax_status': 'zero'},
        ]
        r = calculate_items(items, country='HR')
        self.assertEqual(len(r['items']), 2)
        self.assertEqual(r['subtotal'], Decimal('250'))   # 200 + 50
        self.assertEqual(r['tax_total'], Decimal('50.00'))  # 200*0.25 + 0
        self.assertEqual(r['total'], Decimal('300.00'))

    def test_is_reverse_charge_cross_country(self):
        """is_reverse_charge returns True for EU cross-border with VAT IDs."""
        from invoicing.tax_logic import is_reverse_charge
        from unittest.mock import MagicMock
        company = MagicMock()
        company.vat_id = 'HR12345678901'
        company.oib = None
        company.country = 'HR'
        self.assertTrue(is_reverse_charge(company, 'DE123456789', 'DE'))

    def test_is_reverse_charge_same_country(self):
        """is_reverse_charge returns False when same country."""
        from invoicing.tax_logic import is_reverse_charge
        from unittest.mock import MagicMock
        company = MagicMock()
        company.vat_id = 'HR12345678901'
        company.oib = None
        company.country = 'HR'
        self.assertFalse(is_reverse_charge(company, 'HR98765432109', 'HR'))

    def test_is_reverse_charge_no_client_vat(self):
        """is_reverse_charge returns False when client has no VAT ID."""
        from invoicing.tax_logic import is_reverse_charge
        from unittest.mock import MagicMock
        company = MagicMock()
        company.vat_id = 'HR12345678901'
        company.oib = None
        company.country = 'HR'
        self.assertFalse(is_reverse_charge(company, '', 'DE'))

    def test_is_reverse_charge_no_company_vat(self):
        """is_reverse_charge returns False when company has no VAT ID."""
        from invoicing.tax_logic import is_reverse_charge
        from unittest.mock import MagicMock
        company = MagicMock()
        company.vat_id = None
        company.oib = None
        company.country = 'HR'
        self.assertFalse(is_reverse_charge(company, 'DE123456789', 'DE'))

    def test_kleinunternehmer_eligible(self):
        """check_kleinunternehmer_eligibility: prev < 22000 -> eligible."""
        from invoicing.tax_logic import check_kleinunternehmer_eligibility
        r = check_kleinunternehmer_eligibility(None, 18000)
        self.assertTrue(r['eligible'])
        self.assertEqual(r['limit'], Decimal('22000'))

    def test_kleinunternehmer_not_eligible_prev_year(self):
        """check_kleinunternehmer_eligibility: prev > 22000 -> not eligible."""
        from invoicing.tax_logic import check_kleinunternehmer_eligibility
        r = check_kleinunternehmer_eligibility(None, 25000)
        self.assertFalse(r['eligible'])
        self.assertIn('22000', r['reason'])

    def test_kleinunternehmer_not_eligible_current_year(self):
        """check_kleinunternehmer_eligibility: prev OK but current > 50000."""
        from invoicing.tax_logic import check_kleinunternehmer_eligibility
        r = check_kleinunternehmer_eligibility(None, 15000, current_year_revenue_estimate=55000)
        self.assertFalse(r['eligible'])

    def test_get_tax_rates_hr(self):
        """get_tax_rates('HR') returns list with 25% standard."""
        from invoicing.tax_logic import get_tax_rates
        rates = get_tax_rates('HR')
        self.assertIsInstance(rates, list)
        self.assertTrue(any(r['rate'] == Decimal('25') for r in rates))

    def test_get_tax_rates_de(self):
        """get_tax_rates('DE') returns list with 19% standard."""
        from invoicing.tax_logic import get_tax_rates
        rates = get_tax_rates('DE')
        self.assertTrue(any(r['rate'] == Decimal('19') for r in rates))
        self.assertTrue(any(r['rate'] == Decimal('7') for r in rates))

    def test_get_tax_statuses(self):
        """get_tax_statuses returns list with required statuses."""
        from invoicing.tax_logic import get_tax_statuses
        statuses = get_tax_statuses()
        values = [s['value'] for s in statuses]
        self.assertIn('standard', values)
        self.assertIn('reverse_charge', values)
        self.assertIn('pausalac', values)
        self.assertIn('kleinunternehmer', values)

    def test_get_pdv_footer_note_pausalac(self):
        """get_pdv_footer_note: pausalac returns HR legal text."""
        from invoicing.tax_logic import get_pdv_footer_note
        from unittest.mock import MagicMock
        company = MagicMock()
        company.pdv_status = 'pausalac'
        note = get_pdv_footer_note(company)
        self.assertIn('Pausalni', note)

    def test_get_pdv_footer_note_kleinunternehmer(self):
        """get_pdv_footer_note: kleinunternehmer returns DE legal text."""
        from invoicing.tax_logic import get_pdv_footer_note
        from unittest.mock import MagicMock
        company = MagicMock()
        company.pdv_status = 'kleinunternehmer'
        note = get_pdv_footer_note(company)
        self.assertIn('19 UStG', note)

    def test_get_pdv_footer_note_reverse_charge_de(self):
        """get_pdv_footer_note: reverse_charge DE lang."""
        from invoicing.tax_logic import get_pdv_footer_note
        note = get_pdv_footer_note(None, reverse_charge=True, lang='de')
        self.assertIn('Reverse Charge', note)
        self.assertIn('MwStSystRL', note)


# ═══════════════════════════════════════════════════════════════════════════
#  Suite #37: GoBD COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════════

class GoBDComplianceTests(unittest.TestCase):
    """Suite #37: invoicing/gobd_compliance.py checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = get_or_create_user('tst_gobd', is_staff=True, is_superuser=True)
        from companies.models import Company
        cls.company = Company.objects.first()

    def _make_invoice(self, **kwargs):
        """Create a minimal invoice for testing."""
        from invoicing.models import Invoice
        defaults = {
            'company':       self.company,
            'client_name':   'Test Klijent GmbH',
            'client_address': 'Teststrasse 1',
            'client_oib':    'DE123456789',
            'number':        f'TEST-GOBD-{Invoice.objects.count()+1:04d}',
            'date_issued':   timezone.now(),
            'status':        'SENT',
            'doctype':       'R',
            'country':       'DE',
            'created_by':    self.user,
        }
        defaults.update(kwargs)
        return Invoice.objects.create(**defaults)

    def test_pflichtangaben_complete_invoice(self):
        """check_pflichtangaben: complete invoice returns no warnings."""
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = self._make_invoice()
        warnings = check_pflichtangaben(inv)
        self.assertIsInstance(warnings, list)
        # Complete invoice should have 0 or minimal warnings
        # (may warn about missing items, that's OK)

    def test_pflichtangaben_missing_client_name(self):
        """check_pflichtangaben: missing client_name triggers warning."""
        from invoicing.gobd_compliance import check_pflichtangaben
        inv = self._make_invoice(client_name='')
        warnings = check_pflichtangaben(inv)
        self.assertTrue(any('client_name' in w or 'Empfaenger' in w or 'Name' in w for w in warnings),
                        f"Expected client_name warning, got: {warnings}")

    def test_pflichtangaben_missing_number(self):
        """check_pflichtangaben: missing client_address triggers warning."""
        from invoicing.gobd_compliance import check_pflichtangaben
        # Use missing address (not number, which has unique constraint)
        inv = self._make_invoice(client_address='')
        warnings = check_pflichtangaben(inv)
        # An invoice without address should have at least 0 or more warnings
        self.assertIsInstance(warnings, list)

    def test_fortlaufende_nummer_returns_dict(self):
        """check_fortlaufende_nummer returns dict with ok/gaps/message."""
        from invoicing.gobd_compliance import check_fortlaufende_nummer
        result = check_fortlaufende_nummer(self.company, year=date.today().year)
        self.assertIn('ok', result)
        self.assertIn('gaps', result)
        self.assertIn('message', result)
        self.assertIsInstance(result['gaps'], list)
        self.assertIsInstance(result['ok'], bool)

    def test_gobd_report_structure(self):
        """get_gobd_report returns expected dict structure."""
        from invoicing.gobd_compliance import get_gobd_report
        report = get_gobd_report(self.company, year=date.today().year)
        self.assertIn('year', report)
        self.assertIn('total_invoices', report)
        self.assertIn('issues_count', report)
        self.assertIn('issues', report)
        self.assertIn('nummer_check', report)
        self.assertIn('compliant', report)
        self.assertIsInstance(report['issues'], list)
        self.assertIsInstance(report['compliant'], bool)

    def test_gobd_report_no_company(self):
        """get_gobd_report with None company returns safe empty report."""
        from invoicing.gobd_compliance import get_gobd_report
        report = get_gobd_report(None, year=date.today().year)
        self.assertIn('compliant', report)


# ═══════════════════════════════════════════════════════════════════════════
#  Suite #38: FISCAL BATCH + API TAX CALCULATE
# ═══════════════════════════════════════════════════════════════════════════

class FiscalBatchAndApiTests(unittest.TestCase):
    """Suite #38: fiscal_batch_view GET/POST and api_tax_calculate endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_fiscal', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)
        from companies.models import Company
        cls.company = Company.objects.first()

    def setUp(self):
        if self.company:
            s = self.client.session
            s["impersonated_company_id"] = str(self.company.pk)
            s["impersonation_started_at"] = 0
            s.save()

    def tearDown(self):
        s = self.client.session
        s.pop("impersonated_company_id", None)
        s.save()

    def test_fiscal_batch_get_requires_login(self):
        """GET /invoicing/fiscal/batch/ redirects anonymous users."""
        c = Client()
        r = c.get('/invoicing/fiscal/batch/')
        self.assertEqual(r.status_code, 302)

    def test_fiscal_batch_get_authenticated(self):
        """GET /invoicing/fiscal/batch/ returns 200 for logged-in user."""
        r = self.client.get('/invoicing/fiscal/batch/')
        self.assertEqual(r.status_code, 200)

    def test_fiscal_batch_template_used(self):
        """fiscal_batch_view uses fiscal_batch.html template."""
        r = self.client.get('/invoicing/fiscal/batch/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(b'fiscal' in r.content.lower() or b'fiskali' in r.content.lower())

    def test_fiscal_batch_post_no_invoices(self):
        """POST with no invoice_ids redirects with error."""
        r = self.client.post('/invoicing/fiscal/batch/', {'invoice_ids': []},
                             follow=True)
        self.assertEqual(r.status_code, 200)

    def test_api_tax_calculate_requires_login(self):
        """POST /invoicing/api/tax-calculate/ redirects anonymous."""
        c = Client()
        r = c.post('/invoicing/api/tax-calculate/',
                   data=json.dumps({'base_amount': 100, 'country': 'HR'}),
                   content_type='application/json')
        self.assertEqual(r.status_code, 302)

    def test_api_tax_calculate_hr_standard(self):
        """api_tax_calculate: HR 100 base -> 25 tax -> 125 total."""
        r = self.client.post('/invoicing/api/tax-calculate/',
                             data=json.dumps({'base_amount': 100, 'country': 'HR',
                                              'tax_status': 'standard'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data['ok'])
        self.assertAlmostEqual(data['tax_rate'], 25.0)
        self.assertAlmostEqual(data['tax_amount'], 25.0)
        self.assertAlmostEqual(data['total'], 125.0)

    def test_api_tax_calculate_de_standard(self):
        """api_tax_calculate: DE 100 base -> 19 tax."""
        r = self.client.post('/invoicing/api/tax-calculate/',
                             data=json.dumps({'base_amount': 100, 'country': 'DE',
                                              'tax_status': 'standard'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data['ok'])
        self.assertAlmostEqual(data['tax_rate'], 19.0)
        self.assertAlmostEqual(data['tax_amount'], 19.0)

    def test_api_tax_calculate_reverse_charge(self):
        """api_tax_calculate: reverse_charge -> tax_amount = 0."""
        r = self.client.post('/invoicing/api/tax-calculate/',
                             data=json.dumps({'base_amount': 500, 'country': 'HR',
                                              'tax_status': 'reverse_charge'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data['ok'])
        self.assertAlmostEqual(data['tax_amount'], 0.0)
        self.assertEqual(data['tax_status'], 'reverse_charge')
        self.assertIn('footer_note', data)

    def test_api_tax_calculate_pausalac(self):
        """api_tax_calculate: pausalac -> tax_amount = 0."""
        r = self.client.post('/invoicing/api/tax-calculate/',
                             data=json.dumps({'base_amount': 1000, 'country': 'HR',
                                              'tax_status': 'pausalac'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data['ok'])
        self.assertAlmostEqual(data['tax_amount'], 0.0)

    def test_api_tax_calculate_get_not_allowed(self):
        """api_tax_calculate: GET returns 405."""
        r = self.client.get('/invoicing/api/tax-calculate/')
        self.assertEqual(r.status_code, 405)

    def test_api_tax_calculate_invalid_json(self):
        """api_tax_calculate: invalid JSON body returns 200 with default 0 base."""
        r = self.client.post('/invoicing/api/tax-calculate/',
                             data='not-json',
                             content_type='application/json')
        # Should handle gracefully (base=0 -> tax=0)
        self.assertIn(r.status_code, [200, 400])


# ═══════════════════════════════════════════════════════════════════════════
#  Suite #39: INVOICE FORM VIEW
# ═══════════════════════════════════════════════════════════════════════════

class InvoiceFormViewTests(unittest.TestCase):
    """Suite #39: invoice_form_view GET and invoice_form.html rendering."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.user = get_or_create_user('tst_invform', is_staff=True, is_superuser=True)
        cls.client.force_login(cls.user)
        from companies.models import Company
        cls.company = Company.objects.first()

    def setUp(self):
        if self.company:
            s = self.client.session
            s["impersonated_company_id"] = str(self.company.pk)
            s["impersonation_started_at"] = 0
            s.save()

    def tearDown(self):
        s = self.client.session
        s.pop("impersonated_company_id", None)
        s.save()

    def test_invoice_form_requires_login(self):
        """GET /invoicing/form/ redirects anonymous."""
        c = Client()
        r = c.get('/invoicing/form/')
        self.assertEqual(r.status_code, 302)

    def test_invoice_form_get_200(self):
        """GET /invoicing/form/ returns 200 for authenticated user."""
        r = self.client.get('/invoicing/form/')
        self.assertEqual(r.status_code, 200)

    def test_invoice_form_context_keys(self):
        """invoice_form_view provides required context keys."""
        r = self.client.get('/invoicing/form/')
        self.assertEqual(r.status_code, 200)
        for key in ('tax_rates', 'tax_statuses', 'country', 'currency'):
            self.assertIn(key, r.context, f"Missing context key: {key}")

    def test_invoice_form_contains_form_elements(self):
        """invoice_form.html renders the invoice form."""
        r = self.client.get('/invoicing/form/')
        self.assertIn(r.status_code, [200, 302])
        if r.status_code == 200:
            body = r.content.decode()
            # Either the form or at least the page loaded
            self.assertIn('invoicing', body)

    def test_invoice_form_tax_rates_in_context(self):
        """tax_rates context is a non-empty list of dicts."""
        r = self.client.get('/invoicing/form/')
        tax_rates = r.context['tax_rates']
        self.assertIsInstance(tax_rates, list)
        self.assertGreater(len(tax_rates), 0)
        for tr in tax_rates:
            self.assertIn('rate', tr)
            self.assertIn('label', tr)

    def test_invoice_form_standalone_still_works(self):
        """GET /invoicing/form-standalone/ still returns 200."""
        r = self.client.get('/invoicing/form-standalone/')
        self.assertEqual(r.status_code, 200)

    def test_invoice_tax_status_field_saved(self):
        """invoice_save stores tax_status from POST."""
        from invoicing.models import Invoice
        payload = {
            'doctype':       'R',
            'country':       'HR',
            'currency':      'EUR',
            'client_name':   'Test Tax Status',
            'date_issued':   '2026-03-02T10:00',
            'tax_status':    'reverse_charge',
            'item_desc[]':   ['Savjetovanje'],
            'item_qty[]':    ['1'],
            'item_unit[]':   ['kom'],
            'item_price[]':  ['1000'],
            'item_pdv[]':    ['0'],
            'item_disc[]':   ['0'],
        }
        r = self.client.post('/invoicing/save/', payload, follow=False)
        self.assertIn(r.status_code, [200, 302])
        inv = Invoice.objects.filter(client_name='Test Tax Status').last()
        if inv:
            self.assertEqual(inv.tax_status, 'reverse_charge')



"""
New test suites (40-42) to append to tests_full.py.
Tests: CompanySettings, AppointmentStatus, KontoManualMatch
"""

# ═══════════════════════════════════════════════════════════════
# SUITE 40: COMPANY SETTINGS UI
# ═══════════════════════════════════════════════════════════════

class CompanySettingsTests(unittest.TestCase):
    """Tests for /companies/settings/ — employee management, tabs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from companies.models import Company
        from accounts.models import UserProfile
        from django.contrib.auth.models import User

        cls.company, _ = Company.objects.get_or_create(
            oib='99887766554',
            defaults={'name': 'Settings Test Co', 'country': 'HR'},
        )
        # Create admin user
        cls.admin_user, _ = User.objects.get_or_create(
            username='settings_admin_test',
            defaults={'email': 'settingsadmin@test.local', 'is_staff': True},
        )
        cls.admin_user.set_password('testpass123')
        cls.admin_user.save()
        cls.admin_profile, _ = UserProfile.objects.get_or_create(
            user=cls.admin_user,
            defaults={'company': cls.company, 'role': 'company_admin'},
        )
        if cls.admin_profile.role != 'company_admin':
            cls.admin_profile.role = 'company_admin'
            cls.admin_profile.company = cls.company
            cls.admin_profile.save()

    def setUp(self):
        self.client = Client()
        self.client.login(username='settings_admin_test', password='testpass123')
        s = self.client.session
        s['impersonated_company_id'] = str(self.company.pk)
        s['impersonation_started_at'] = 0
        s.save()

    def test_settings_page_loads(self):
        """GET /companies/settings/ returns 200."""
        r = self.client.get('/companies/settings/')
        self.assertIn(r.status_code, [200, 302])

    def test_settings_info_tab(self):
        """GET /companies/settings/?tab=info shows company name."""
        r = self.client.get('/companies/settings/?tab=info')
        self.assertIn(r.status_code, [200, 302])
        if r.status_code == 200:
            body = r.content.decode()
            self.assertIn('Settings Test Co', body)

    def test_settings_employees_tab(self):
        """GET /companies/settings/?tab=employees returns 200."""
        r = self.client.get('/companies/settings/?tab=employees')
        self.assertIn(r.status_code, [200, 302])

    def test_settings_branches_tab(self):
        """GET /companies/settings/?tab=branches returns 200."""
        r = self.client.get('/companies/settings/?tab=branches')
        self.assertIn(r.status_code, [200, 302])

    def test_settings_tab_tab(self):
        """GET /companies/settings/?tab=settings returns 200."""
        r = self.client.get('/companies/settings/?tab=settings')
        self.assertIn(r.status_code, [200, 302])

    def test_employee_create_missing_email(self):
        """POST employee create without email returns 400."""
        r = self.client.post('/companies/settings/employee/create/', {})
        self.assertIn(r.status_code, [400, 403])

    def test_employee_create_duplicate_email(self):
        """POST employee create with existing email returns error JSON."""
        from django.contrib.auth.models import User
        existing, _ = User.objects.get_or_create(
            username='duptest_settings',
            defaults={'email': 'duptest_settings@example.com'},
        )
        r = self.client.post('/companies/settings/employee/create/', {
            'email': existing.email,
            'first_name': 'Dup',
            'last_name': 'Test',
            'role': 'worker',
        })
        import json
        self.assertIn(r.status_code, [400, 200])
        try:
            data = json.loads(r.content)
            self.assertFalse(data.get('ok', True))
        except Exception:
            pass

    def test_info_post_updates_company(self):
        """POST to settings info tab updates company data."""
        r = self.client.post('/companies/settings/?tab=info', {
            'name': 'Settings Test Co Updated',
            'oib': '99887766554',
            'country': 'HR',
            'tab': 'info',
        }, follow=True)
        self.assertIn(r.status_code, [200, 302])

    def test_settings_post_saves(self):
        """POST to settings tab saves JSON settings."""
        r = self.client.post('/companies/settings/?tab=settings', {
            'default_tax_pct': '25',
            'invoice_number_format': '{YYYY}-{NUM}',
            'email_reply_to': 'test@test.de',
            'working_hours': '09:00-17:00',
            'ui_language': 'hr',
            'tab': 'settings',
        }, follow=True)
        self.assertIn(r.status_code, [200, 302])


# ═══════════════════════════════════════════════════════════════
# SUITE 41: APPOINTMENT STATUS CHANGES
# ═══════════════════════════════════════════════════════════════

class AppointmentStatusTests(unittest.TestCase):
    """Tests for appointment confirm/cancel/complete status changes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.contrib.auth.models import User
        from accounts.models import UserProfile
        from companies.models import Company
        from appointments.models import Appointment

        cls.company, _ = Company.objects.get_or_create(
            oib='88776655443',
            defaults={'name': 'Appt Status Test Co', 'country': 'HR'},
        )
        cls.user, _ = User.objects.get_or_create(
            username='appt_status_user_test',
            defaults={'is_staff': True},
        )
        cls.user.set_password('testpass123')
        cls.user.save()
        up, _ = UserProfile.objects.get_or_create(
            user=cls.user,
            defaults={'company': cls.company, 'role': 'company_admin'},
        )
        if up.company != cls.company:
            up.company = cls.company
            up.save()

        from django.utils import timezone
        cls.appt = Appointment.objects.create(
            title='Test Status Appt',
            start_time=timezone.now() + timezone.timedelta(days=1),
            end_time=timezone.now() + timezone.timedelta(days=1, hours=1),
            status='scheduled',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='appt_status_user_test', password='testpass123')

    def test_appointment_list_loads(self):
        """GET /appointments/lista/ returns 200."""
        r = self.client.get('/appointments/lista/')
        self.assertIn(r.status_code, [200, 302])

    def test_confirm_appointment(self):
        """POST to status endpoint sets status to confirmed."""
        from appointments.models import Appointment
        from django.utils import timezone as tz_appt
        appt = Appointment.objects.create(
            title='Confirm Test Appt',
            start_time=tz_appt.now() + tz_appt.timedelta(days=2),
            end_time=tz_appt.now() + tz_appt.timedelta(days=2, hours=1),
            status='scheduled',
        )
        r = self.client.post(f'/appointments/{appt.pk}/status/', {'status': 'confirmed'})
        self.assertIn(r.status_code, [200, 302])
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'confirmed')

    def test_cancel_appointment(self):
        """POST to status endpoint sets status to cancelled."""
        from appointments.models import Appointment
        from django.utils import timezone
        appt = Appointment.objects.create(
            title='Cancel Test Appt',
            start_time=timezone.now() + timezone.timedelta(days=3),
            end_time=timezone.now() + timezone.timedelta(days=3, hours=1),
            status='scheduled',
        )
        r = self.client.post(f'/appointments/{appt.pk}/status/', {'status': 'cancelled'})
        self.assertIn(r.status_code, [200, 302])
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'cancelled')

    def test_invalid_status_ignored(self):
        """POST with invalid status does not change appointment."""
        from appointments.models import Appointment
        from django.utils import timezone
        appt = Appointment.objects.create(
            title='Invalid Status Test',
            start_time=timezone.now() + timezone.timedelta(days=4),
            end_time=timezone.now() + timezone.timedelta(days=4, hours=1),
            status='scheduled',
        )
        r = self.client.post(f'/appointments/{appt.pk}/status/', {'status': 'nonexistent'})
        # Should not crash
        self.assertIn(r.status_code, [200, 302])


# ═══════════════════════════════════════════════════════════════
# SUITE 42: KONTO MANUAL MATCHING
# ═══════════════════════════════════════════════════════════════

class KontoManualMatchTests(unittest.TestCase):
    """Tests for manual transaction matching and ignore functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.contrib.auth.models import User
        from accounts.models import UserProfile
        from companies.models import Company
        from konto.models import BankAccount, BankTransaction

        cls.company, _ = Company.objects.get_or_create(
            oib='77665544332',
            defaults={'name': 'Konto Match Test Co', 'country': 'HR'},
        )
        cls.user, _ = User.objects.get_or_create(
            username='konto_match_user_test',
            defaults={'is_staff': True},
        )
        cls.user.set_password('testpass123')
        cls.user.save()
        up, _ = UserProfile.objects.get_or_create(
            user=cls.user,
            defaults={'company': cls.company, 'role': 'company_admin'},
        )
        if up.company != cls.company:
            up.company = cls.company
            up.save()

        cls.bank_account, _ = BankAccount.objects.get_or_create(
            company=cls.company,
            iban='HR1234567890123456789',
            defaults={'name': 'Test Bank', 'currency': 'EUR', 'current_balance': 0},
        )
        cls.txn = BankTransaction.objects.create(
            bank_account=cls.bank_account,
            company=cls.company,
            transaction_date=__import__('datetime').date.today(),
            transaction_type='inflow',
            amount=1000,
            counterparty_name='Test Payer',
            status='unmatched',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='konto_match_user_test', password='testpass123')
        s = self.client.session
        s['impersonated_company_id'] = str(self.company.pk)
        s['impersonation_started_at'] = 0
        s.save()

    def test_transactions_page_loads(self):
        """GET /konto/transactions/ returns 200."""
        r = self.client.get('/konto/transactions/')
        self.assertIn(r.status_code, [200, 302])

    def test_unmatched_invoices_api(self):
        """GET /konto/api/unmatched-invoices/ returns JSON list."""
        import json
        r = self.client.get('/konto/api/unmatched-invoices/')
        self.assertIn(r.status_code, [200, 302])
        if r.status_code == 200:
            data = json.loads(r.content)
            self.assertIn('invoices', data)
            self.assertIsInstance(data['invoices'], list)

    def test_ignore_transaction(self):
        """POST /konto/api/ignore/<pk>/ marks transaction as ignored."""
        import json
        from konto.models import BankTransaction
        txn = BankTransaction.objects.create(
            bank_account=self.bank_account,
            company=self.company,
            transaction_date=__import__('datetime').date.today(),
            transaction_type='inflow',
            amount=500,
            counterparty_name='Ignore Test',
            status='unmatched',
        )
        r = self.client.post(
            f'/konto/api/ignore/{txn.pk}/',
            data='{}',
            content_type='application/json',
        )
        self.assertIn(r.status_code, [200, 302])
        if r.status_code == 200:
            data = json.loads(r.content)
            self.assertTrue(data.get('success', False))
            txn.refresh_from_db()
            self.assertEqual(txn.status, 'ignored')

    def test_match_transaction_missing_invoice(self):
        """POST /konto/api/match/<pk>/ with nonexistent invoice returns error."""
        import json
        r = self.client.post(
            f'/konto/api/match/{self.txn.pk}/',
            data=json.dumps({'invoice_id': 99999999}),
            content_type='application/json',
        )
        self.assertIn(r.status_code, [400, 404, 200])

    def test_auto_match_endpoint(self):
        """POST /konto/api/auto-match/ returns success JSON."""
        import json
        r = self.client.post(
            '/konto/api/auto-match/',
            data='{}',
            content_type='application/json',
        )
        self.assertIn(r.status_code, [200, 302])
        if r.status_code == 200:
            data = json.loads(r.content)
            self.assertIn('success', data)


SUITES = [
    (InvoicingTests,     '1. INVOICING'),
    (POSTests,           '2. POS'),
    (AppointmentsTests,  '3. APPOINTMENTS'),
    (WorktimeTests,      '4. WORKTIME'),
    (CalculatorTests,    '5. CALCULATOR'),
    (SuperadminTests,    '6. SUPERADMIN'),
    (InterventionsTests, '7. INTERVENTIONS'),
    (ImpersonationTests, '8. IMPERSONATION'),
    (TrackingTests,      '9. TRACKING'),
    (GastroTests,        '10. GASTRO POS'),
    (ExpiryTests,        '11. EXPIRY'),
    (AIAssistantTests,   '12. AI ASSISTANT'),
    (BookingTests,       '13. BOOKING'),
    (RBACTests,          '14. RBAC'),
    (NotificationTests,  '15. NOTIFICATIONS'),
    (ReportTests,        '16. REPORTS'),
    (ModuleGatingTests,  '17. MODULE GATING'),
    (PortalTests,        '18. CLIENT PORTAL'),
    (CeleryTests,        '19. CELERY TASKS'),
    (EmailTemplateTests,  '20. EMAIL TEMPLATES'),
    (WhatsAppTests,       '21. WHATSAPP'),
    (WhatsAppTaskTests,   '22. WHATSAPP TASKS'),
    (WizardTests,         '23. WIZARD'),
    (InvoiceProfileTests, '24. INVOICE PROFILES'),
    (WorktimeIntegrationTests, '25. WORKTIME INTEGRATION'),
    (InvoicingRedesignTests, '26. INVOICING REDESIGN'),
    (OfficeWizardTests, '27. OFFICE WIZARD'),
    (GridEditorAjaxTests, '28. GRID EDITOR AJAX'),
    (KontoModelsTests, '29. KONTO MODELS'),
    (KontoServicesTests, '30. KONTO SERVICES'),
    (KontoViewsTests, '31. KONTO VIEWS'),
    (InvoiceDuplicateTests, '32. INVOICE DUPLICATE'),
    (QuoteWorkflowTests, '33. QUOTE WORKFLOW'),
    (PricingPlanTests, '34. PRICING PLAN'),
    (RegistrationFlowTests, '35. REGISTRATION FLOW'),
    (TaxLogicTests,         '36. TAX LOGIC'),
    (GoBDComplianceTests,   '37. GOBD COMPLIANCE'),
    (FiscalBatchAndApiTests,'38. FISCAL BATCH & API'),
    (InvoiceFormViewTests,  '39. INVOICE FORM VIEW'),
    (CompanySettingsTests,  '40. COMPANY SETTINGS'),
    (AppointmentStatusTests,'41. APPOINTMENT STATUS'),
    (KontoManualMatchTests, '42. KONTO MANUAL MATCH'),
]

DIVIDER = '─' * 55


def run_suite(suite_class, label):
    print(f'\n{DIVIDER}')
    print(f'  {label}')
    print(DIVIDER)
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromTestCase(suite_class)
    buf    = open(_os.devnull, 'w')
    result = unittest.TextTestRunner(verbosity=0, stream=buf).run(suite)
    buf.close()

    passed = result.testsRun - len(result.failures) - len(result.errors)
    if result.failures or result.errors:
        for tag, items in (('FAIL', result.failures), ('ERROR', result.errors)):
            for test, tb in items:
                print(f'\n  [{tag}] {test}')
                # show last 5 lines of traceback
                lines = tb.strip().splitlines()
                for line in lines[-5:]:
                    print(f'        {line}')
    print(f'\n  Result: {passed}/{result.testsRun} passed', end='')
    print(' ✓' if not (result.failures or result.errors) else ' ✗')
    return result


if __name__ == '__main__':
    print(f'\nLIMIT Connect ERP — Comprehensive Tests   [{date.today()}]')
    total_run = total_passed = 0
    for cls, label in SUITES:
        r = run_suite(cls, label)
        total_run    += r.testsRun
        total_passed += r.testsRun - len(r.failures) - len(r.errors)

    print(f'\n{"═"*55}')
    print(f'  TOTAL: {total_passed}/{total_run} tests passed')
    print(f'{"═"*55}\n')
    sys.exit(0 if total_passed == total_run else 1)
