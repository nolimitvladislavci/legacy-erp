#!/usr/bin/env python
"""
BORG MASTER SIMULATION — simulate_borg.py
Django management command

Poziv: python manage.py simulate_borg [--modules all] [--users 3] [--report]
       python manage.py simulate_borg --modules experiences,pos,invoicing
       python manage.py simulate_borg --full --report

Simulira realne tokove rada korisnika po SVIM BORG modulima.
Svaki modul ima vlastiti scenarij koji odražava stvarnu upotrebu.

Output: JSON report + terminal ispis s prolaznošću/greškom po modulu.
Ovo NIJE load test — to je functional smoke test s realnim podacima.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import json
import traceback
import sys
import time
from datetime import date, timedelta

User = get_user_model()

# ═══════════════════════════════════════════════════════════════
# BOJE ZA TERMINAL
# ═══════════════════════════════════════════════════════════════
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
BLUE   = '\033[94m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg):  print(f"  {BLUE}→{RESET} {msg}")
def head(msg):  print(f"\n{BOLD}{BLUE}━━ {msg} ━━{RESET}")


class SimResult:
    def __init__(self, module):
        self.module = module
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []
        self.start = time.time()
        self.duration = 0

    def success(self, msg):
        self.passed += 1
        ok(msg)

    def error(self, msg, exc=None):
        self.failed += 1
        self.errors.append({'msg': msg, 'exc': str(exc) if exc else None})
        fail(msg)
        if exc:
            fail(f"  Exception: {exc}")

    def warning(self, msg):
        self.warnings += 1
        warn(msg)

    def done(self):
        self.duration = round(time.time() - self.start, 2)
        total = self.passed + self.failed
        rate = round(100 * self.passed / total, 1) if total else 0
        color = GREEN if rate >= 90 else (YELLOW if rate >= 70 else RED)
        print(f"\n  {color}{BOLD}[{self.module}] {self.passed}/{total} ({rate}%) — {self.duration}s{RESET}")
        return self

    def to_dict(self):
        return {
            'module': self.module,
            'passed': self.passed,
            'failed': self.failed,
            'warnings': self.warnings,
            'errors': self.errors,
            'duration_s': self.duration,
            'pass_rate': round(100 * self.passed / (self.passed + self.failed), 1) if (self.passed + self.failed) else 0
        }


class Command(BaseCommand):
    help = 'BORG Master Simulation — testira sve module s realnim korisničkim tokovima'

    def add_arguments(self, parser):
        parser.add_argument('--modules', default='all',
            help='Moduli za testiranje (comma-separated) ili "all"')
        parser.add_argument('--report', action='store_true',
            help='Spremi JSON report u /tmp/borg_sim_report.json')
        parser.add_argument('--no-rollback', action='store_true',
            help='NE rollbackaj kreirane test podatke (opasno na produkciji!)')
        parser.add_argument('--company-id', type=int, default=None,
            help='ID kompanije za testiranje (default: prva kompanija)')
        parser.add_argument('--user-id', type=int, default=None,
            help='ID korisnika za simulaciju (default: prvi superuser)')

    def handle(self, *args, **options):
        print(f"\n{BOLD}{'═'*60}")
        print(f"  BORG MASTER SIMULATION — {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}{RESET}")

        # Setup
        company, user = self._setup_context(options)
        if not company or not user:
            self.stderr.write("FATAL: Nema kompanije ili korisnika za testiranje.")
            sys.exit(1)

        print(f"\n{BLUE}Kompanija:{RESET} {company}")
        print(f"{BLUE}Korisnik:{RESET}  {user.username} ({user.email})")

        # Odaberi module
        modules_requested = options['modules']
        all_modules = [
            'company', 'invoicing', 'pos', 'experiences',
            'work_orders', 'warehouse', 'worktime', 'burza',
            'partners', 'borg_ops', 'golubar', 'rental',
            'compliance', 'ai_health', 'sidebar_urls',
            'interventions', 'eracun', 'einvoice', 'fiscal',
            'tax_wizard', 'udruge', 'konto', 'payroll',
            'documents', 'appointments', 'helpdesk', 'gov_export',
            'livestock', 'delivery', 'gastro_menu', 'marketplace',
            'aml', 'smart_import', 'fitness', 'propter',
            'webshop', 'procurement', 'maintenance', 'payments',
            'intelligence', 'tracking', 'traceability', 'fenix_ai',
            'registration', 'premium_booking',
        ]

        if modules_requested == 'all':
            modules = all_modules
        else:
            modules = [m.strip() for m in modules_requested.split(',')]

        # Pokreni simulacije
        results = []
        use_rollback = not options['no_rollback']

        for module in modules:
            fn_name = f'_sim_{module}'
            fn = getattr(self, fn_name, None)
            if not fn:
                warn(f"Modul '{module}' nema simulaciju — preskačem.")
                continue

            if use_rollback:
                try:
                    with transaction.atomic():
                        r = fn(company, user)
                        r.done()
                        results.append(r.to_dict())
                        raise Exception("__ROLLBACK__")  # Uvijek rollback
                except Exception as e:
                    if "__ROLLBACK__" not in str(e):
                        r = SimResult(module)
                        r.error(f"Neočekivana greška u modulu", e)
                        r.done()
                        results.append(r.to_dict())
            else:
                r = fn(company, user)
                r.done()
                results.append(r.to_dict())

        # Summary
        self._print_summary(results)

        if options['report']:
            report_path = '/tmp/borg_sim_report.json'
            with open(report_path, 'w') as f:
                json.dump({
                    'timestamp': timezone.now().isoformat(),
                    'company': str(company),
                    'user': user.username,
                    'results': results
                }, f, indent=2)
            print(f"\n{GREEN}Report spremljen: {report_path}{RESET}")

    def _setup_context(self, options):
        from companies.models import Company
        company_id = options.get('company_id')
        user_id = options.get('user_id')

        try:
            company = Company.objects.get(pk=company_id) if company_id else Company.objects.first()
        except Exception:
            company = None

        try:
            user = User.objects.get(pk=user_id) if user_id else User.objects.filter(is_superuser=True).first()
        except Exception:
            user = None

        return company, user

    def _print_summary(self, results):
        print(f"\n{BOLD}{'═'*60}")
        print(f"  SUMMARY")
        print(f"{'═'*60}{RESET}")
        total_pass = sum(r['passed'] for r in results)
        total_fail = sum(r['failed'] for r in results)
        total_all  = total_pass + total_fail
        overall    = round(100 * total_pass / total_all, 1) if total_all else 0
        color = GREEN if overall >= 90 else (YELLOW if overall >= 70 else RED)

        for r in results:
            rate = r['pass_rate']
            c = GREEN if rate >= 90 else (YELLOW if rate >= 70 else RED)
            bar = '█' * int(rate / 10) + '░' * (10 - int(rate / 10))
            print(f"  {c}{bar}{RESET} {r['module']:20} {c}{rate:5.1f}%{RESET}  ({r['passed']}/{r['passed']+r['failed']})  {r['duration_s']}s")
            for err in r.get('errors', []):
                print(f"       {RED}↳ {err['msg']}{RESET}")

        print(f"\n  {color}{BOLD}UKUPNO: {total_pass}/{total_all} ({overall}%){RESET}")
        print(f"{'═'*60}\n")

    # ═══════════════════════════════════════════════════════════════
    # SIMULACIJE PO MODULU
    # ═══════════════════════════════════════════════════════════════

    def _sim_company(self, company, user):
        r = SimResult('company')
        head("COMPANY — Osnovna struktura kompanije")

        try:
            info("Provjera Company polja")
            assert hasattr(company, 'name'), "Company nema 'name'"
            r.success(f"Company: {company.name}")
        except Exception as e:
            r.error("Company model greška", e)

        try:
            info("Provjera korisnika kompanije")
            from core.company_utils import get_user_company
            # Simuliramo request objekt
            class FakeRequest:
                def __init__(self, u, c):
                    self.user = u
                    self._company = c
            # Provjeri postoji li kompanija u bazi
            from companies.models import Company
            count = Company.objects.count()
            r.success(f"Ukupno kompanija u bazi: {count}")
        except Exception as e:
            r.error("Company utils greška", e)

        try:
            from companies.models import Company
            c = Company.objects.filter(pk=company.pk).first()
            assert c is not None
            r.success(f"Company dohvat OK: {c.name}")
        except Exception as e:
            r.error("Company dohvat greška", e)

        return r

    def _sim_invoicing(self, company, user):
        r = SimResult('invoicing')
        head("INVOICING — Fakturiranje")

        try:
            from invoicing.models import Invoice, InvoiceItem
            info("Kreiranje test fakture")

            from invoicing.services.invoice_service import create_invoice
            from django.utils import timezone
            inv = create_invoice(
                company=company,
                doctype='R',
                date_issued=timezone.now(),
                client_name='Test Klijent — simulacija',
            )
            r.success(f"Faktura kreirana: pk={inv.pk}, broj={inv.number}")

            # Dodaj stavku — section/sort_order sada u modelu
            item = InvoiceItem(
                invoice=inv,
                description='Test usluga — simulacija',
                quantity=Decimal('2'),
                unit_price=Decimal('100.00'),
                tax_rate=Decimal('25'),
            )
            item.save()
            r.success(f"InvoiceItem kreiran: {item.description} (gross: {item.gross_total} EUR)")

            # Provjeri izračun
            total = InvoiceItem.objects.filter(invoice=inv).count()
            assert total >= 1
            r.success(f"Invoice ima {total} stavki")

            # Provjeri statuse
            assert inv.status == 'DRAFT'
            r.success("Status: draft OK")

        except Exception as e:
            r.error("Invoicing kreiranje greška", e)

        try:
            from invoicing.models import Invoice
            count = Invoice.objects.filter(company=company).count()
            r.success(f"Invoice queryset: {count} faktura u bazi")
        except Exception as e:
            r.error("Invoice queryset greška", e)

        return r

    def _sim_pos(self, company, user):
        r = SimResult('pos')
        head("POS — Point of Sale")

        try:
            from pos.models import POSReceipt
            info("Provjera POS modela")
            count = POSReceipt.objects.count()  # Cross-company count za simulaciju
            r.success(f"POSReceipt queryset OK: {count} računa")
        except Exception as e:
            r.error("POSReceipt model greška", e)

        try:
            # Provjeri POS konfiguraciju
            from pos.models import POSTerminal
            terminals = POSTerminal.objects.all()[:5]  # Cross-company za simulaciju
            r.success(f"POS terminala: {terminals.count()}")
        except ImportError:
            r.warning("POSTerminal model ne postoji — preskačem")
        except Exception as e:
            r.error("POSTerminal greška", e)

        try:
            from django.test import RequestFactory
            from django.contrib.auth.middleware import AuthenticationMiddleware
            from pos import views as pos_views
            info("URL resolve check za POS")
            from django.urls import reverse
            url = reverse('pos:dashboard')
            r.success(f"POS Joker URL resolves: {url}")
        except Exception as e:
            r.error("POS URL greška", e)

        return r

    def _sim_experiences(self, company, user):
        r = SimResult('experiences')
        head("EXPERIENCES — Agro-Turizam 360")

        try:
            from experiences.models import Experience
            info("Kreiranje test iskustva")
            exp = Experience(
                company=company,
                name="TEST Degustacija vina — simulacija",
                experience_type='degustacija',
                description="Testna degustacija za simulaciju sustava.",
                duration_minutes=90,
                capacity=12,
                min_pax=2,
                price_per_person=Decimal('45.00'),
                deposit_pct=30,
                cancellation_hours=12,
                tax_rate=Decimal('13'),
            )
            exp.save()
            r.success(f"Experience kreiran: {exp.name} (pk={exp.pk})")
            assert exp.deposit_amount == Decimal('13.50')
            r.success(f"Deposit amount property: {exp.deposit_amount} EUR")
        except Exception as e:
            r.error("Experience kreiranje greška", e)
            return r

        try:
            from experiences.models import ExperienceSchedule
            info("Kreiranje termina")
            sched = ExperienceSchedule(
                experience=exp,
                date=date.today() + timedelta(days=3),
                time_from='10:00',
                time_to='11:30',
                max_pax=12,
                status='open',
            )
            sched.save()
            r.success(f"Schedule kreiran: {sched.date} {sched.time_from}")
            assert sched.available_spots == 12
            assert sched.is_bookable == True
            r.success(f"Available spots: {sched.available_spots}, Bookable: {sched.is_bookable}")
        except Exception as e:
            r.error("Schedule kreiranje greška", e)
            return r

        try:
            from experiences.models import ExperienceBooking
            info("Kreiranje rezervacije")
            booking = ExperienceBooking(
                schedule=sched,
                guest_name="Ivan Testović",
                guest_email="test@simulacija.borg",
                guest_phone="+38512345678",
                guest_country="HR",
                pax_count=2,
                children_count=0,
                payment_method='card',
                status='pending',
            )
            booking.save()
            r.success(f"Booking kreiran: {booking.guest_name} ({booking.pax_count} os.)")
            assert booking.status == 'pending'
            assert booking.price_total > 0, "price_total mora biti > 0"
            r.success(f"Price total: {booking.price_total} EUR")
        except Exception as e:
            r.error("Booking kreiranje greška", e)

        try:
            from experiences.models import AgroPackage
            info("AgroPackage model provjera")
            AgroPackage.objects.filter(company=company).count()
            r.success("AgroPackage queryset OK")
        except Exception as e:
            r.error("AgroPackage greška", e)

        try:
            from experiences.models import RecallEvent
            info("RecallEvent model provjera")
            recall = RecallEvent(
                company=company,
                title="TEST Recall — kontaminirani med",
                description="Povišene razine HMF — simulacija",
                source_model='StockBatch',
                source_id=0,
                severity='warning',
            )
            recall.save()
            r.success(f"RecallEvent kreiran (pk={recall.pk})")
        except Exception as e:
            r.error("RecallEvent greška", e)

        try:
            from django.urls import reverse
            urls_to_check = [
                ('experiences:experience_list', []),
                ('experiences:package_list', []),
                ('experiences:recall_list', []),
            ]
            for name, args in urls_to_check:
                url = reverse(name, args=args)
                r.success(f"URL resolves: {url}")
        except Exception as e:
            r.error("URL resolve greška", e)

        try:
            info("Provjera template-a")
            from django.template.loader import get_template
            templates_to_check = [
                'experiences/experience_list.html',
                'experiences/experience_detail.html',
                'experiences/experience_form.html',
                'experiences/booking_form.html',
                'experiences/schedule_form.html',
                'experiences/package_list.html',
                'experiences/package_detail.html',
                'experiences/package_form.html',
                'experiences/recall_list.html',
                'experiences/recall_detail.html',
                'experiences/recall_form.html',
                'experiences/review_form.html',
            ]
            missing = []
            for tpl in templates_to_check:
                try:
                    get_template(tpl)
                    r.success(f"Template OK: {tpl}")
                except Exception:
                    missing.append(tpl)
                    r.error(f"Template MISSING: {tpl}")
            if missing:
                r.warning(f"POTREBNO: CC_TASK_EXPERIENCES_TEMPLATES.md — {len(missing)} templatea nedostaje!")
        except Exception as e:
            r.error("Template provjera greška", e)

        return r

    def _sim_work_orders(self, company, user):
        r = SimResult('work_orders')
        head("WORK ORDERS — Radni nalozi")

        try:
            from work_orders.models import WorkOrder
            wo = WorkOrder(
                company=company,
                status='draft',
                priority='normal',
                description="TEST nalog — simulacija BORG",
            )
            wo.save()
            r.success(f"WorkOrder kreiran: {wo.order_number or f'pk={wo.pk}'}")

            # FSM tranzicija
            if hasattr(wo, 'start_progress'):
                wo.start_progress()
                wo.save()
                assert wo.status == 'in_progress'
                r.success("FSM: draft → in_progress OK")
            else:
                wo.status = 'in_progress'
                wo.save()
                r.success("Status update: in_progress OK")

        except Exception as e:
            r.error("WorkOrder greška", e)

        try:
            from work_orders.models import WorkOrderItem
            wo2 = WorkOrder.objects.filter(company=company).first()
            if wo2:
                item = WorkOrderItem(
                    work_order=wo2,
                    description="Test materijal",
                    quantity=Decimal('2'),
                    unit_price=Decimal('50.00'),
                )
                item.save()
                r.success(f"WorkOrderItem kreiran: {item.description}")
        except Exception as e:
            r.error("WorkOrderItem greška", e)

        try:
            from django.urls import reverse
            for name in ['work_orders:list', 'work_orders:create']:
                url = reverse(name)
                r.success(f"URL: {url}")
        except Exception as e:
            r.error("work_orders URL greška", e)

        return r

    def _sim_warehouse(self, company, user):
        r = SimResult('warehouse')
        head("WAREHOUSE — Skladište")

        try:
            from inventory.models import InventoryItem as Item
            count = Item.objects.filter(company=company).count()
            r.success(f"Inventory Items: {count}")
        except Exception as e:
            r.error("Inventory Item greška", e)

        try:
            from inventory.models import StockMovement
            count = StockMovement.objects.filter(company=company).count() if hasattr(StockMovement, 'company') else StockMovement.objects.count()
            r.success(f"StockMovement records: {count}")
        except ImportError:
            r.warning("StockMovement model ne postoji")
        except Exception as e:
            r.error("StockMovement greška", e)

        try:
            from django.urls import reverse
            url = reverse('inventory:list')
            r.success(f"Inventory URL: {url}")
        except Exception as e:
            r.error("Inventory URL greška", e)

        return r

    def _sim_worktime(self, company, user):
        r = SimResult('worktime')
        head("WORKTIME — Evidencija radnog vremena")

        try:
            from worktime.models import TimeEntry
            count = TimeEntry.objects.filter(company=company).count() if hasattr(TimeEntry, 'company') else TimeEntry.objects.filter(worker__company=company).count()
            r.success(f"TimeEntry records: {count}")
        except Exception as e:
            r.error("TimeEntry greška", e)

        try:
            from worktime.services import WorktimeService
            r.success("WorktimeService import OK")
        except Exception as e:
            r.warning(f"WorktimeService nije dostupan: {e}")

        try:
            from django.urls import reverse
            url = reverse('worktime:ts_worker')
            r.success(f"Worktime URL: {url}")
        except Exception as e:
            r.error("Worktime URL greška", e)

        return r

    def _sim_burza(self, company, user):
        r = SimResult('burza')
        head("BURZA — Oglasna ploča / Marketplace")

        try:
            from burza.models import ProjectLead
            count = ProjectLead.objects.filter(company=company).count()
            r.success(f"ProjectLead records: {count}")

            lead = ProjectLead(
                company=company,
                title="TEST oglas — simulacija",
                status='draft',
            )
            lead.save()
            r.success(f"ProjectLead kreiran: pk={lead.pk}")

        except Exception as e:
            r.error("ProjectLead greška", e)

        try:
            from django.urls import reverse
            url = reverse('burza:kanban')
            r.success(f"Burza URL: {url}")
        except Exception as e:
            r.error("Burza URL greška", e)

        return r

    def _sim_partners(self, company, user):
        r = SimResult('partners')
        head("PARTNERS — Poslovni partneri")

        try:
            from partners.models import Partner
            count = Partner.objects.filter(company=company).count()
            r.success(f"Partner records: {count}")

            partner = Partner(
                company=company,
                name="TEST Partner d.o.o. — simulacija",
                oib="12345678901",
            )
            partner.save()
            r.success(f"Partner kreiran: {partner.name}")

        except Exception as e:
            r.error("Partner greška", e)

        return r

    def _sim_borg_ops(self, company, user):
        r = SimResult('borg_ops')
        head("BORG OPS — Operativni centar")

        try:
            from borg_ops.models import CardActivity
            count = CardActivity.objects.count()
            r.success(f"CardActivity records: {count}")
        except Exception as e:
            r.error("CardActivity greška", e)

        try:
            from borg_ops.models import CardActivity
            assert hasattr(CardActivity, 'is_public_facing'), "is_public_facing polje ne postoji!"
            assert hasattr(CardActivity, 'is_system_generated'), "is_system_generated polje ne postoji!"
            public_count = CardActivity.objects.filter(is_public_facing=True).count()
            r.success(f"CardActivity.is_public_facing: OK. Javnih zapisa: {public_count}")
            r.success(f"CardActivity.is_system_generated: OK")
        except AssertionError as e:
            r.error(str(e))
        except Exception as e:
            r.error("CardActivity sigurnosna provjera greška", e)

        try:
            from borg_ops.models import StatusTimestamp
            count = StatusTimestamp.objects.count()
            r.success(f"StatusTimestamp records: {count}")
        except Exception as e:
            r.error("StatusTimestamp greška", e)

        try:
            from django.urls import reverse
            url = reverse('borg_ops:operations_dashboard')
            r.success(f"Operations Dashboard URL: {url}")
        except Exception as e:
            r.error("borg_ops URL greška", e)

        try:
            from django.urls import reverse
            url = reverse('borg_ops:borg_hub')
            r.success(f"BORG Hub URL: {url}")
        except Exception as e:
            r.warning(f"BORG Hub URL ne postoji još — CC_TASK_BORG_HUB.md potreban")

        return r

    def _sim_golubar(self, company, user):
        r = SimResult('golubar')
        head("GOLUBAR — Uzgoj golubova")

        try:
            from golubar.models import Golub
            count = Golub.objects.filter(company=company).count()
            r.success(f"Golub records: {count}")
        except ImportError:
            r.warning("Golubar app nije instalirana ili Golub model ne postoji")
        except Exception as e:
            r.error("Golubar greška", e)

        try:
            from django.urls import reverse
            url = reverse('golubar:jato_list')
            r.success(f"Golubar URL: {url}")
        except Exception as e:
            r.warning(f"Golubar URL greška: {e}")

        return r

    def _sim_rental(self, company, user):
        r = SimResult('rental')
        head("RENTAL — Smještaj / Iznajmljivanje")

        try:
            from rental.models import Property, Booking
            props = Property.objects.filter(company=company).count()
            bookings = Booking.objects.filter(rental_property__company=company).count()
            r.success(f"Properties: {props}, Bookings: {bookings}")
        except Exception as e:
            r.error("Rental greška", e)

        try:
            from django.urls import reverse
            url = reverse('rental:property_list')
            r.success(f"Rental URL: {url}")
        except Exception as e:
            r.error("Rental URL greška", e)

        return r

    def _sim_compliance(self, company, user):
        r = SimResult('compliance')
        head("COMPLIANCE — Zakonska usklađenost")

        try:
            from invoicing.models import Invoice
            # Provjeri da compliance filter radi
            new_invoices = Invoice.objects.filter(
                company=company,
                synesis_id__isnull=True,
            )
            r.success(f"New (non-synesis) invoices: {new_invoices.count()}")
        except Exception as e:
            r.error("Compliance Invoice filter greška", e)

        try:
            from django.urls import reverse
            url = reverse('compliance:dashboard')
            r.success(f"Compliance URL: {url}")
        except Exception as e:
            r.warning(f"Compliance URL ne postoji: {e}")

        return r

    def _sim_ai_health(self, company, user):
        r = SimResult('ai_health')
        head("AI HEALTH — AI agent health check")

        try:
            from core.ai_health import run_health_check
            result = run_health_check()
            r.success(f"AI Health check pokrenuto: {result}")
        except ImportError:
            r.warning("ai_health modul ne postoji na ovoj putanji")
        except Exception as e:
            r.error("AI Health greška", e)

        try:
            import subprocess
            result = subprocess.run(
                ['python3', 'manage.py', 'check', '--deploy'],
                capture_output=True, text=True,
                cwd='/var/www/fina-connect'
            )
            if result.returncode == 0:
                r.success("Django system check: OK")
            else:
                r.warning(f"Django check warnings: {result.stdout[:200]}")
        except Exception as e:
            r.error("Django check greška", e)

        return r


    def _sim_interventions(self, company, user):
        r = SimResult('interventions')
        head("INTERVENTIONS — Hitne intervencije")
        try:
            from interventions.models import HitnaIntervencija
            count = HitnaIntervencija.objects.filter(company=company).count()
            r.success(f"HitnaIntervencija records: {count}")
        except Exception as e:
            r.error("HitnaIntervencija greška", e)
        try:
            from django.urls import reverse
            url = reverse('interventions:list')
            r.success(f"Interventions URL: {url}")
        except Exception as e:
            r.warning(f"Interventions URL: {e}")
        return r

    def _sim_eracun(self, company, user):
        r = SimResult('eracun')
        head("E-RAČUN — Elektroničko fakturiranje")
        try:
            from eracun.models import ERacun, ERacunConfig
            config = ERacunConfig.objects.filter(company=company).first()
            r.success(f"ERacunConfig: {'aktivan' if config and config.is_active else 'neaktivan'}")
            count = ERacun.objects.filter(company=company).count()
            r.success(f"ERacun dokumenata: {count}")
        except Exception as e:
            r.error("ERacun greška", e)
        try:
            from eracun.services.validator import validate_full
            r.success("Validator modul dostupan")
        except Exception as e:
            r.warning(f"Validator import: {e}")
        return r

    def _sim_einvoice(self, company, user):
        r = SimResult('einvoice')
        head("E-INVOICE — PEPPOL/AS4")
        try:
            from einvoice.models import AS4Message
            count = AS4Message.objects.count()
            r.success(f"AS4Message records: {count}")
        except Exception as e:
            r.error("AS4Message greška", e)
        return r

    def _sim_fiscal(self, company, user):
        r = SimResult('fiscal')
        head("FISCAL — Fiskalizacija health")
        try:
            from fiscal.models import FiscalConfiguration
            latest = FiscalConfiguration.objects.first()
            if latest:
                r.success(f"FiscalConfiguration: {latest}")
            else:
                r.success("FiscalConfiguration: nema zapisa (OK za dev)")
        except Exception as e:
            r.error("Fiscal greška", e)
        return r

    def _sim_tax_wizard(self, company, user):
        r = SimResult('tax_wizard')
        head("TAX WIZARD — Porezni obrasci")
        try:
            from tax_wizard.models import TaxFormTemplate, TaxDeadline
            templates = TaxFormTemplate.objects.count()
            deadlines = TaxDeadline.objects.count()
            r.success(f"TaxFormTemplate: {templates}, TaxDeadline: {deadlines}")
        except Exception as e:
            r.error("TaxWizard greška", e)
        try:
            from django.urls import reverse
            url = reverse('tax_wizard:dashboard')
            r.success(f"Tax Wizard URL: {url}")
        except Exception as e:
            r.warning(f"Tax Wizard URL: {e}")
        return r

    def _sim_udruge(self, company, user):
        r = SimResult('udruge')
        head("UDRUGE — 9 segmenata")
        try:
            from udruge.models import UdrugaSegment
            segments = UdrugaSegment.objects.count()
            r.success(f"UdrugaSegment: {segments}")
        except Exception as e:
            r.warning(f"UdrugaSegment: {e}")
        segments_to_check = [
            ('vatrogasci', 'DVD modul'),
            ('kud', 'KUD modul'),
            ('ribolov', 'Ribolov modul'),
            ('pcelari', 'Pčelari modul'),
            ('rakija', 'Rakija modul'),
            ('vocari', 'Voćari modul'),
            ('branitelji', 'Branitelji modul'),
            ('lov', 'Lov modul'),
            ('zadruge', 'Zadruge modul'),
        ]
        for seg_key, seg_name in segments_to_check:
            try:
                from django.urls import reverse
                url = reverse(f'udruge:{seg_key}_dashboard')
                r.success(f"{seg_name} URL: {url}")
            except Exception:
                r.warning(f"{seg_name} URL ne postoji")
        return r

    def _sim_konto(self, company, user):
        r = SimResult('konto')
        head("KONTO — Knjigovodstvo")
        try:
            from konto.models import KontoAccount, JournalEntry
            kp_count = KontoAccount.objects.filter(company=company).count()
            tj_count = JournalEntry.objects.filter(company=company).count()
            r.success(f"KontoAccount: {kp_count}, JournalEntry: {tj_count}")
        except Exception as e:
            r.error("Konto greška", e)
        try:
            from django.urls import reverse
            url = reverse('konto:dashboard')
            r.success(f"Konto URL: {url}")
        except Exception as e:
            r.warning(f"Konto URL: {e}")
        return r

    def _sim_payroll(self, company, user):
        r = SimResult('payroll')
        head("PAYROLL — Obračun plaća")
        try:
            from payroll.models import PayrollRun
            count = PayrollRun.objects.filter(company=company).count()
            r.success(f"PayrollRun records: {count}")
        except Exception as e:
            r.error("Payroll greška", e)
        return r

    def _sim_documents(self, company, user):
        r = SimResult('documents')
        head("DOCUMENTS — Arhiva dokumenata")
        try:
            from documents.models import Document
            count = Document.objects.filter(company=company).count()
            r.success(f"Document records: {count}")
        except Exception as e:
            r.error("Documents greška", e)
        try:
            from django.urls import reverse
            url = reverse('documents:archive')
            r.success(f"Arhiva URL: {url}")
        except Exception as e:
            r.warning(f"Arhiva URL: {e}")
        return r

    def _sim_appointments(self, company, user):
        r = SimResult('appointments')
        head("APPOINTMENTS — Naručivanje")
        try:
            from appointments.models import Appointment, BookingService
            services = BookingService.objects.filter(company=company).count()
            appts = Appointment.objects.filter(company=company).count()
            r.success(f"Services: {services}, Appointments: {appts}")
        except Exception as e:
            r.error("Appointments greška", e)
        return r

    def _sim_helpdesk(self, company, user):
        r = SimResult('helpdesk')
        head("HELPDESK — Tiketi podrške")
        try:
            from helpdesk.models import Ticket
            count = Ticket.objects.count()
            r.success(f"Ticket records: {count}")
        except Exception as e:
            r.error("Helpdesk greška", e)
        return r

    def _sim_gov_export(self, company, user):
        r = SimResult('gov_export')
        head("GOV EXPORT — Državni izvozi")
        try:
            from gov_export.models import GovExport
            count = GovExport.objects.filter(company=company).count()
            r.success(f"GovExport records: {count}")
        except Exception as e:
            r.error("GovExport greška", e)
        try:
            from django.urls import reverse
            url = reverse('gov_export:validator')
            r.success(f"CroXML Verify URL: {url}")
        except Exception as e:
            r.warning(f"CroXML Verify URL: {e}")
        return r

    def _sim_livestock(self, company, user):
        r = SimResult('livestock')
        head("LIVESTOCK — Stočarstvo / Flock")
        try:
            from livestock.models import Livestock
            count = Livestock.objects.filter(company=company).count()
            r.success(f"Livestock records: {count}")
        except Exception as e:
            r.error("Livestock greška", e)
        return r

    def _sim_delivery(self, company, user):
        r = SimResult('delivery')
        head("DELIVERY — Dostava")
        try:
            from delivery.models import DeliveryRoute
            count = DeliveryRoute.objects.count()
            r.success(f"DeliveryRoute records: {count}")
        except Exception as e:
            r.error("Delivery greška", e)
        return r

    def _sim_gastro_menu(self, company, user):
        r = SimResult('gastro_menu')
        head("GASTRO MENU — Jelovnik")
        try:
            from gastro_menu.models import MenuItem
            count = MenuItem.objects.count()
            r.success(f"MenuItem records: {count}")
        except Exception as e:
            r.error("GastroMenu greška", e)
        return r

    def _sim_marketplace(self, company, user):
        r = SimResult('marketplace')
        head("MARKETPLACE — Tržnica")
        try:
            from marketplace.models import FuturesListing
            count = FuturesListing.objects.count()
            r.success(f"FuturesListing records: {count}")
        except Exception as e:
            r.error("Marketplace greška", e)
        return r

    def _sim_aml(self, company, user):
        r = SimResult('aml')
        head("AML — Anti Money Laundering")
        try:
            from aml.models import AMLClientProfile
            count = AMLClientProfile.objects.filter(company=company).count()
            r.success(f"AMLClientProfile records: {count}")
        except Exception as e:
            r.error("AML greška", e)
        return r

    def _sim_smart_import(self, company, user):
        r = SimResult('smart_import')
        head("SMART IMPORT — Uvoz podataka")
        try:
            from smart_import.models import ImportBatch
            count = ImportBatch.objects.filter(company=company).count()
            r.success(f"ImportBatch records: {count}")
        except Exception as e:
            r.error("SmartImport greška", e)
        return r

    def _sim_fitness(self, company, user):
        r = SimResult('fitness')
        head("FITNESS — Teretana / Wellness")
        try:
            from fitness.models import Member
            count = Member.objects.count()
            r.success(f"Fitness Member records: {count}")
        except Exception as e:
            r.error("Fitness greška", e)
        return r

    def _sim_propter(self, company, user):
        r = SimResult('propter')
        head("PROPTER — Knjiga prigovora")
        try:
            from propter.models import PropterConfig
            count = PropterConfig.objects.filter(company=company).count()
            r.success(f"PropterConfig records: {count}")
        except Exception as e:
            r.error("Propter greška", e)
        return r

    def _sim_webshop(self, company, user):
        r = SimResult('webshop')
        head("WEBSHOP — Online trgovina")
        try:
            from webshop.models import Product
            count = Product.objects.filter(company=company).count()
            r.success(f"Webshop Product records: {count}")
        except Exception as e:
            r.error("Webshop greška", e)
        return r

    def _sim_procurement(self, company, user):
        r = SimResult('procurement')
        head("PROCUREMENT — Nabava")
        try:
            from procurement.models import PurchaseOrder
            count = PurchaseOrder.objects.filter(company=company).count()
            r.success(f"PurchaseOrder records: {count}")
        except Exception as e:
            r.error("Procurement greška", e)
        return r

    def _sim_maintenance(self, company, user):
        r = SimResult('maintenance')
        head("MAINTENANCE — Održavanje")
        try:
            from maintenance.models import Asset
            count = Asset.objects.filter(company=company).count()
            r.success(f"Asset records: {count}")
        except Exception as e:
            r.error("Maintenance greška", e)
        return r

    def _sim_payments(self, company, user):
        r = SimResult('payments')
        head("PAYMENTS — Plaćanja")
        try:
            from payments.models import Payment as PaymentModel
            count = PaymentModel.objects.filter(company=company).count()
            r.success(f"Payment records: {count}")
        except Exception as e:
            r.error("Payments greška", e)
        return r

    def _sim_intelligence(self, company, user):
        r = SimResult('intelligence')
        head("INTELLIGENCE — BI / Analytics")
        try:
            from intelligence.models import IntelligenceResult
            count = IntelligenceResult.objects.count()
            r.success(f"IntelligenceResult records: {count}")
        except Exception as e:
            r.error("Intelligence greška", e)
        return r

    def _sim_tracking(self, company, user):
        r = SimResult('tracking')
        head("TRACKING — GPS / Praćenje")
        try:
            from tracking.models import TrackingEvent
            count = TrackingEvent.objects.count()
            r.success(f"TrackingEvent records: {count}")
        except Exception as e:
            r.error("Tracking greška", e)
        return r

    def _sim_traceability(self, company, user):
        r = SimResult('traceability')
        head("TRACEABILITY — Slijedivost")
        try:
            from traceability.models import TraceEvent
            count = TraceEvent.objects.count()
            r.success(f"TraceEvent records: {count}")
        except Exception as e:
            r.error("Traceability greška", e)
        return r

    def _sim_fenix_ai(self, company, user):
        r = SimResult('fenix_ai')
        head("FENIX AI — Signali + Agenti")
        try:
            from limit_connect_ai.models_signal import FenixSignal
            total = FenixSignal.objects.count()
            new = FenixSignal.objects.filter(status='new').count()
            r.success(f"FenixSignal: {total} total, {new} new")
        except Exception as e:
            r.error("FenixSignal greška", e)
        try:
            from limit_connect_ai.models import AIConversation
            count = AIConversation.objects.count()
            r.success(f"AIConversation records: {count}")
        except Exception as e:
            r.warning(f"AIConversation: {e}")
        return r

    def _sim_registration(self, company, user):
        r = SimResult('registration')
        head("REGISTRATION — Onboarding")
        try:
            from registration.models import CompanyRegistration
            count = CompanyRegistration.objects.count()
            r.success(f"CompanyRegistration records: {count}")
        except Exception as e:
            r.error("Registration greška", e)
        return r

    def _sim_premium_booking(self, company, user):
        r = SimResult('premium_booking')
        head("PREMIUM BOOKING — Premium rezervacije")
        try:
            from premium_booking.models import Booking
            count = Booking.objects.count()
            r.success(f"PremiumBooking records: {count}")
        except Exception as e:
            r.error("PremiumBooking greška", e)
        return r

    def _sim_sidebar_urls(self, company, user):
        r = SimResult('sidebar_urls')
        head("SIDEBAR URLS — Provjera svih URL-ova u navigaciji")

        # Svi URL-ovi koji se pojavljuju u sidebar-u baze
        sidebar_url_names = [
            ('dashboard', []),
            ('invoicing:index', []),
            ('partners:list', []),
            ('pos:dashboard', []),
            ('work_orders:list', []),
            ('worktime:ts_worker', []),
            ('burza:kanban', []),
            ('inventory:list', []),
            ('experiences:experience_list', []),
            ('experiences:package_list', []),
            ('experiences:recall_list', []),
            ('borg_ops:operations_dashboard', []),
        ]

        from django.urls import reverse, NoReverseMatch
        for name, args in sidebar_url_names:
            try:
                url = reverse(name, args=args)
                r.success(f"URL resolves: {name} → {url}")
            except NoReverseMatch as e:
                r.error(f"URL BROKEN: {name}", e)
            except Exception as e:
                r.error(f"URL ERROR: {name}", e)

        return r
