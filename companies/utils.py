from django.db import DatabaseError


def get_managed_companies(user):
    """
    Vraća queryset firmi kojima korisnik ima pristup kao partner/reseller.
    Uključuje vlastitu firmu + sve aktivno upravljane firme.
    """
    from .models import Company, CompanyPartnership

    try:
        membership = user.company_memberships.filter(is_active=True, is_default=True).first()
        if membership is None:
            # Fallback: UserProfile company
            from accounts.models import UserProfile

            profile = UserProfile.objects.filter(user=user).first()
            user_company = profile.company if profile else None
        else:
            user_company = membership.company
        if user_company is None:
            return Company.objects.none()
    except (DatabaseError, AttributeError):
        return Company.objects.none()

    # Vlastita firma + aktivno upravljane
    managed_ids = CompanyPartnership.objects.filter(
        partner_company=user_company,
        valid_until__isnull=True,  # aktivan odnos
    ).values_list("managed_company_id", flat=True)

    return Company.objects.filter(id__in=list(managed_ids) + [user_company.id]).order_by("name")
