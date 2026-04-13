"""
FSM Policy Export — čita SVE transition pravila iz koda i generira
jedinstven, mašinski čitljiv dokument.

Izvori:
1. FSMMixin.TRANSITIONS (WorkOrder, ProjectLead, HitnaIntervencija)
2. invoicing VALID_TRANSITIONS (ne koristi FSMMixin)
3. appointments VALID_STATUS_TRANSITIONS (ne koristi FSMMixin)
4. experiences ExperienceBooking.STATUS_CHOICES (implicitno u mark_no_show/cancel/etc.)

Usage:
  python manage.py export_fsm_policy              # Terminal output
  python manage.py export_fsm_policy --json        # JSON export
  python manage.py export_fsm_policy --markdown    # Markdown export
"""

import json

from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export svih FSM transition pravila iz koda"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="JSON output")
        parser.add_argument("--markdown", action="store_true", help="Markdown output")

    def handle(self, *args, **options):
        policies = []

        # ── 1. FSMMixin subclasses ──
        try:
            from borg_ops.mixins import FSMMixin

            for model in apps.get_models():
                if issubclass(model, FSMMixin) and model is not FSMMixin:
                    if hasattr(model, "TRANSITIONS") and model.TRANSITIONS:
                        policies.append(
                            {
                                "model": f"{model._meta.app_label}.{model.__name__}",
                                "source": "FSMMixin.TRANSITIONS",
                                "status_field": getattr(model, "STATUS_FIELD", "status"),
                                "transitions": model.TRANSITIONS,
                            }
                        )
        except ImportError:
            pass

        # ── 2. Invoicing VALID_TRANSITIONS ──
        try:
            from invoicing.services.invoice_service import VALID_TRANSITIONS

            policies.append(
                {
                    "model": "invoicing.Invoice",
                    "source": "invoicing.services.invoice_service.VALID_TRANSITIONS",
                    "status_field": "status",
                    "transitions": VALID_TRANSITIONS,
                }
            )
        except ImportError:
            pass

        # ── 3. Appointments VALID_STATUS_TRANSITIONS ──
        try:
            from appointments.services import VALID_STATUS_TRANSITIONS

            policies.append(
                {
                    "model": "appointments.Appointment",
                    "source": "appointments.services.VALID_STATUS_TRANSITIONS",
                    "status_field": "status",
                    "transitions": VALID_STATUS_TRANSITIONS,
                }
            )
        except ImportError:
            pass

        # ── 4. Experiences booking (implicit from STATUS_CHOICES) ──
        try:
            from experiences.models import ExperienceBooking  # noqa: F401

            policies.append(
                {
                    "model": "experiences.ExperienceBooking",
                    "source": "experiences.models (implicit)",
                    "status_field": "status",
                    "transitions": {
                        "pending": ["confirmed", "cancelled"],
                        "confirmed": ["checked_in", "no_show", "cancelled"],
                        "checked_in": ["completed"],
                        "completed": [],
                        "no_show": [],
                        "cancelled": [],
                    },
                }
            )
        except ImportError:
            pass

        # ── Output ──
        if options["json"]:
            self.stdout.write(json.dumps(policies, indent=2, ensure_ascii=False))
        elif options["markdown"]:
            self._output_markdown(policies)
        else:
            self._output_terminal(policies)

        self.stderr.write(
            self.style.SUCCESS(
                f"\n{len(policies)} FSM policies exported from {len(set(p['source'] for p in policies))} sources"
            )
        )

    def _output_terminal(self, policies):
        for p in policies:
            self.stdout.write(f"\n{'=' * 60}")
            self.stdout.write(self.style.SUCCESS(f"  {p['model']}"))
            self.stdout.write(f"  Source: {p['source']}")
            self.stdout.write(f"  Field: {p['status_field']}")
            self.stdout.write(f"  {'─' * 56}")
            for from_status, to_list in p["transitions"].items():
                if to_list:
                    arrows = " | ".join(to_list)
                    self.stdout.write(f"  {from_status:20s} → {arrows}")
                else:
                    self.stdout.write(self.style.WARNING(f"  {from_status:20s} → (terminal)"))

    def _output_markdown(self, policies):
        self.stdout.write("# FSM Policy Document\n")
        self.stdout.write(f"Generated: {__import__('django.utils.timezone', fromlist=['now']).now().isoformat()}\n")
        for p in policies:
            self.stdout.write(f"\n## {p['model']}\n")
            self.stdout.write(f"- **Source:** `{p['source']}`\n")
            self.stdout.write(f"- **Field:** `{p['status_field']}`\n\n")
            self.stdout.write("| From | To | Terminal |\n|------|----|---------|\n")
            for from_status, to_list in p["transitions"].items():
                to_str = ", ".join(to_list) if to_list else "—"
                terminal = "YES" if not to_list else ""
                self.stdout.write(f"| {from_status} | {to_str} | {terminal} |\n")
