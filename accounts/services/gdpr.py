"""
accounts/services/gdpr.py

GDPR Compliance Services:
- GDPRExportService  -- Clanak 20: Pravo na prenosivost podataka (JSON export)
- GDPRAnonymizationService -- Clanak 17: Pravo na brisanje (kriptografska anonimizacija)

VAZNO: Financijski zapisi (fakture, knjizenja, fiskalni racuni) se NE brisu
jer su zasticeni Zakonom o racunovodstvu (11 godina). Umjesto toga,
osobni podaci se zamjenjuju placeholder vrijednostima.
"""
import json
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger(__name__)


class GDPRExportService:
    """Clanak 20 GDPR -- Pravo na prenosivost podataka."""

    @staticmethod
    def generate_export(user):
        data = {
            "metadata": {
                "generated_at": timezone.now(),
                "system": "LIMIT Connect",
                "gdpr_article": "Clanak 20 -- Pravo na prenosivost podataka",
            },
            "user_account": {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
            },
        }

        # UserProfile
        try:
            up = user.userprofile
            data["profile"] = {
                "role": up.role,
                "phone": up.phone,
                "department": up.department,
                "preferred_language": up.preferred_language,
                "last_login_ip": up.last_login_ip,
                "created_at": up.created_at,
            }
        except Exception:
            pass

        # EmployeeProfile
        try:
            ep = user.employeeprofile
            data["employment"] = {
                "employee_id": ep.employee_id,
                "tax_id": ep.tax_id,
                "address": ep.address,
                "bank_account": ep.bank_account,
                "phone": ep.phone,
                "department": ep.department,
                "position": ep.position,
                "hourly_rate": str(ep.hourly_rate),
                "overtime_rate": str(ep.overtime_rate),
            }
        except Exception:
            pass

        # CompanyMembership
        try:
            from accounts.models import CompanyMembership
            memberships = CompanyMembership.objects.filter(user=user).select_related("company")
            data["company_memberships"] = [
                {"company": m.company.name, "role": m.role, "is_active": m.is_active, "joined_at": m.joined_at}
                for m in memberships
            ]
        except DatabaseError:
            pass

        # DeviceToken
        try:
            from accounts.models import DeviceToken
            tokens = DeviceToken.objects.filter(user=user)
            data["device_tokens"] = [
                {"device_name": t.device_name, "is_active": t.is_active, "created_at": t.created_at, "last_used_at": t.last_used_at, "last_ip": t.last_ip}
                for t in tokens
            ]
        except DatabaseError:
            pass

        # Login pokusaji (zadnjih 100)
        try:
            from accounts.auth_models import LoginAttempt
            attempts = LoginAttempt.objects.filter(email=user.email).order_by("-attempted_at")[:100]
            data["recent_login_activity"] = [
                {"time": a.attempted_at, "ip": a.ip_address, "success": a.success, "method": a.method}
                for a in attempts
            ]
        except DatabaseError:
            pass

        return json.dumps(data, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)


class GDPRAnonymizationService:
    """Clanak 17 GDPR -- Pravo na brisanje (anonimizacija)."""

    @staticmethod
    @transaction.atomic
    def anonymize_user(user):
        result = {"user_id": user.pk, "actions": []}
        anon_id = f"deleted_{user.pk}"

        # 1. UserProfile
        try:
            up = user.userprofile
            up.phone = ""
            up.profile_image = ""
            up.totp_secret = ""
            up.totp_enabled = False
            up.two_factor_secret = ""
            up.two_factor_enabled = False
            up.google_id = ""
            up.microsoft_id = ""
            up.push_subscription = ""
            up.last_login_ip = None
            up.save()
            result["actions"].append("UserProfile anonimizirano")
        except (IntegrityError, DatabaseError):
            pass

        # 2. EmployeeProfile (zadrzavamo OIB/IBAN ako postoje payroll zapisi)
        try:
            ep = user.employeeprofile
            has_payroll = False
            try:
                from payroll.models import PayrollRun
                has_payroll = PayrollRun.objects.filter(company=ep.company).exists()
            except DatabaseError:
                pass

            ep.address = ""
            ep.phone = ""
            ep.position = ""
            ep.department = ""
            if not has_payroll:
                ep.tax_id = ""
                ep.bank_account = ""
                result["actions"].append("EmployeeProfile potpuno anonimizirano")
            else:
                result["actions"].append("EmployeeProfile anonimizirano (OIB/IBAN sacuvani -- payroll)")
            ep.save()
        except (IntegrityError, DatabaseError):
            pass

        # 3. DeviceToken brisanje
        try:
            from accounts.models import DeviceToken
            count = DeviceToken.objects.filter(user=user).count()
            DeviceToken.objects.filter(user=user).delete()
            if count:
                result["actions"].append(f"{count} DeviceToken obrisano")
        except (IntegrityError, DatabaseError):
            pass

        # 4. User model (ZADNJE)
        original_email = user.email
        user.first_name = "Obrisan"
        user.last_name = "Korisnik"
        user.email = f"{anon_id}@anonymized.local"
        user.username = anon_id
        user.is_active = False
        user.set_unusable_password()
        user.save()
        result["actions"].append("User account deaktiviran i anonimiziran")

        # 5. Audit zapis -- dokaz GDPR brisanja
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                user=None,
                company=None,
                action="delete",
                model_name="accounts.User",
                object_id=str(user.pk),
                object_repr=f"GDPR Anonimizacija -- bivsi korisnik {anon_id}",
                changes={
                    "gdpr_action": "anonymization",
                    "original_email_hash": str(hash(original_email)),
                    "timestamp": timezone.now().isoformat(),
                    "actions_performed": result["actions"],
                },
                ip_address=None,
            )
            result["actions"].append("SystemAuditLog zapis kreiran")
        except (IntegrityError, DatabaseError) as e:
            logger.error("GDPR audit log greska: %s", e)

        logger.info("GDPR anonimizacija zavrsena za korisnika %s. Akcije: %s", user.pk, result["actions"])
        return result
