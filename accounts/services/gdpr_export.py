"""
GDPR Data Portability — Članak 20.
Agregator osobnih podataka korisnika u strojno čitljivom JSON formatu.

Pravila:
- Eksportira SAMO osobne podatke tražitelja (Data Subject)
- NE eksportira: totp_secret, push_subscription, password hash
- NE eksportira: poslovne podatke tvrtke (to je poslovna tajna)
- SystemAuditLog: max 1000 zapisa (OOM zaštita)
"""

import json
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger(__name__)


class GDPRExportService:
    """Agregator osobnih podataka po čl. 20 GDPR-a."""

    MAX_AUDIT_RECORDS = 1000

    @staticmethod
    def generate_export(user) -> str:
        """
        Generiraj kompletni JSON export osobnih podataka korisnika.
        Returns: JSON string (pretty-printed, UTF-8).
        """
        data = {
            "metadata": {
                "export_date": timezone.now().isoformat(),
                "system": "LIMIT Connect ERP",
                "system_url": "https://limit-connect.com",
                "regulatory_basis": "GDPR Article 20 — Right to Data Portability",
                "data_subject": user.username,
                "format": "JSON (RFC 8259)",
            },
            # ── auth.User model ──────────────────────────────────────
            "account": {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_joined": user.date_joined.isoformat() if user.date_joined else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "is_active": user.is_active,
            },
        }

        # ── UserProfile (related_name='profile') ────────────────────
        profile = getattr(user, "profile", None)
        if profile:
            data["profile"] = {
                "role": profile.role,
                "phone": profile.phone,
                "department": profile.department,
                "preferred_language": getattr(profile, "preferred_language", ""),
                "google_id_linked": bool(getattr(profile, "google_id", "")),
                "microsoft_id_linked": bool(getattr(profile, "microsoft_id", "")),
                "2fa_enabled": getattr(profile, "totp_enabled", False),
                "can_upload_photos": getattr(profile, "can_upload_photos", True),
                "can_view_financials": getattr(profile, "can_view_financials", False),
                "can_approve_timesheets": getattr(profile, "can_approve_timesheets", False),
                "created_at": profile.created_at.isoformat()
                if hasattr(profile, "created_at") and profile.created_at
                else None,
                "last_login_ip": getattr(profile, "last_login_ip", None),
            }
            if profile.profile_image:
                data["profile"]["profile_image_path"] = profile.profile_image.name
            # IZRIČITO NE eksportiramo:
            # - totp_secret (sigurnosni ključ)
            # - two_factor_secret (backup)
            # - push_subscription (endpoint token)

        # ── CompanyMembership ────────────────────────────────────────
        try:
            from accounts.models import CompanyMembership

            memberships = CompanyMembership.objects.filter(
                user=user,
            ).select_related("company")

            if memberships.exists():
                data["company_memberships"] = [
                    {
                        "company_name": m.company.name,
                        "role": m.role,
                        "is_default": m.is_default,
                        "is_active": m.is_active,
                        "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    }
                    for m in memberships
                ]
        except DatabaseError as e:
            logger.debug("GDPR: CompanyMembership skip: %s", e)

        # ── SystemAuditLog (digitalni trag) ──────────────────────────
        try:
            from core.models import SystemAuditLog

            audits = SystemAuditLog.objects.filter(
                user=user,
            ).order_by("-timestamp")[: GDPRExportService.MAX_AUDIT_RECORDS]

            if audits.exists():
                data["audit_trail"] = {
                    "note": f"Zadnjih {GDPRExportService.MAX_AUDIT_RECORDS} zapisa (iz sigurnosnih razloga)",
                    "records": [
                        {
                            "timestamp": log.timestamp.isoformat(),
                            "action": log.action,
                            "model": log.model_name,
                            "object": log.object_repr[:100] if log.object_repr else "",
                            "ip_address": log.ip_address,
                        }
                        for log in audits
                    ],
                }
        except DatabaseError as e:
            logger.debug("GDPR: AuditLog skip: %s", e)

        # ── ImpersonationLog (tko je pristupio kao ovaj korisnik) ────
        try:
            from accounts.models import ImpersonationLog

            imps = ImpersonationLog.objects.filter(
                user=user,
            ).order_by("-started_at")[:100]

            if imps.exists():
                data["impersonation_log"] = [
                    {
                        "superadmin": imp.superadmin.username if imp.superadmin else "?",
                        "started_at": imp.started_at.isoformat() if imp.started_at else None,
                        "ended_at": imp.ended_at.isoformat() if imp.ended_at else None,
                        "ip_address": getattr(imp, "ip_address", None),
                    }
                    for imp in imps
                ]
        except DatabaseError as e:
            logger.debug("GDPR: ImpersonationLog skip: %s", e)

        # ── DeviceTokens ─────────────────────────────────────────────
        try:
            from accounts.models import DeviceToken

            tokens = DeviceToken.objects.filter(user=user)
            if tokens.exists():
                data["device_tokens"] = [
                    {
                        "device_name": t.device_name,
                        "created_at": t.created_at.isoformat() if hasattr(t, "created_at") else None,
                        "last_used": getattr(t, "last_used", None),
                    }
                    for t in tokens
                ]
        except DatabaseError:
            pass

        # ── Consent records ──────────────────────────────────────────
        data["consent"] = {
            "note": "Pristanak na uvjete korištenja i politiku privatnosti",
            "has_signed_tc": getattr(profile, "has_signed_tc", None) if profile else None,
        }

        data["metadata"]["total_fields_exported"] = _count_fields(data)

        return json.dumps(data, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)


def _count_fields(obj, count=0):
    """Broji ukupan broj osobnih podataka u exportu."""
    if isinstance(obj, dict):
        for v in obj.values():
            count = _count_fields(v, count)
    elif isinstance(obj, list):
        for item in obj:
            count = _count_fields(item, count)
    else:
        count += 1
    return count
