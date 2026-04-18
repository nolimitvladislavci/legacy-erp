"""
Fenix v3 — Accounts Views | 13/10

Login flow:
1. User unese credentials (ili glasovno)
2. LoginAudit se kreira (GDPR)
3. Ako ima membership → active_company_id u session
4. Redirect na dashboard

Svaki view: HTMX + AI hint + pristupačnost + glasovni unos.
"""
import logging
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from core.base_view import FenixView, PublicView
from .models import LoginAudit, CompanyMembership

logger = logging.getLogger("fenix.accounts")


class LoginView(PublicView):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return self.render(request)

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        ip = self._get_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:500]

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Audit — success
            LoginAudit.objects.create(
                user=user,
                username_attempted=username,
                ip_address=ip,
                user_agent=user_agent,
                success=True,
            )

            # Set active company from default membership
            membership = (
                CompanyMembership.objects
                .filter(user=user, is_deleted=False)
                .order_by("-is_default", "-created_at")
                .select_related("company")
                .first()
            )
            if membership:
                request.session["active_company_id"] = str(membership.company_id)

            logger.info(f"Login OK: {username} from {ip}")
            return redirect("accounts:dashboard")
        else:
            # Audit — failure
            LoginAudit.objects.create(
                username_attempted=username,
                ip_address=ip,
                user_agent=user_agent,
                success=False,
                failure_reason="invalid_credentials",
            )

            logger.warning(f"Login FAIL: {username} from {ip}")
            messages.error(request, "Neispravno korisničko ime ili lozinka.")

            if self.is_htmx():
                return self.render(request, {"username": username}, status=422)
            return self.render(request, {"username": username})

    def _get_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "127.0.0.1")


class LogoutView(FenixView):
    def get(self, request):
        logout(request)
        messages.success(request, "Uspješno ste se odjavili.")
        return redirect("accounts:login")


class DashboardView(FenixView):
    template_name = "accounts/dashboard.html"
    page_title = "Dashboard"

    def get_ai_hint(self, context):
        company = context.get("company")
        if company:
            return f"Dobrodošli u {company.display_name}. Kako vam mogu pomoći danas?"
        return "Dobrodošli u Fenix. Odaberite tvrtku za početak rada."

    def get(self, request):
        company = self.get_company()

        # Get user's memberships for company switcher
        memberships = (
            CompanyMembership.objects
            .filter(user=request.user, is_deleted=False)
            .select_related("company")
            .order_by("-is_default", "company__name")
        )

        ctx = {
            "memberships": memberships,
            "company_count": memberships.count(),
        }

        return self.render(request, ctx)


class CompanySwitchView(FenixView):
    """HTMX endpoint: mijenja aktivnu firmu bez full page reload."""

    def post(self, request):
        company_id = request.POST.get("company_id")
        if not company_id:
            return self.json_error("Nedostaje company_id")

        membership = (
            CompanyMembership.objects
            .filter(user=request.user, company_id=company_id, is_deleted=False)
            .select_related("company")
            .first()
        )

        if not membership:
            return self.json_error("Nemate pristup toj tvrtki", status=403)

        request.session["active_company_id"] = str(company_id)
        messages.success(request, f"Prebačeno na: {membership.company.display_name}")

        if self.is_htmx():
            return self.htmx_refresh()
        return redirect("accounts:dashboard")
