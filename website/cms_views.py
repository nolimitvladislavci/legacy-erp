from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .models import GalleryImage


@login_required
def cms_gallery(request):
    if not (
        request.user.is_superuser
        or (hasattr(request.user, "profile") and request.user.profile.role in ["company_admin", "superadmin"])
    ):
        return redirect("/")

    if request.method == "POST":
        image = request.FILES.get("image")
        category = request.POST.get("category", "bau")
        caption_de = request.POST.get("caption_de", "")
        caption_hr = request.POST.get("caption_hr", "")
        if image:
            GalleryImage.objects.create(
                image=image, category=category, caption_de=caption_de, caption_hr=caption_hr, is_active=True, order=0
            )
            messages.success(request, _("Slika uspješno dodana!"))
        return redirect("website:cms_gallery")

    images = GalleryImage.objects.all().order_by("-id")
    return render(request, "website/cms/gallery_manager.html", {"images": images})


@login_required
def toggle_img(request, id):
    if request.method == "POST":
        try:
            img = GalleryImage.objects.get(id=id)
            img.is_active = not img.is_active
            img.save()
            return JsonResponse({"ok": True, "is_active": img.is_active})
        except ObjectDoesNotExist:
            pass
    return JsonResponse({"ok": False})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MULTI-TENANT WEBSITE BUILDER — CMS VIEWS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _get_site_for_user(user):
    """Return CompanyWebsite for the user, creating one if missing. Returns None on error."""
    from .models import CompanyWebsite

    try:
        company = user.profile.company
    except AttributeError:
        return None
    slug_base = getattr(company, "booking_slug", None) or company.oib or str(company.pk)
    site, _ = CompanyWebsite.objects.get_or_create(
        company=company,
        defaults={
            "slug": slug_base,
            "site_title": company.name,
        },
    )
    return site


def _is_editor(user):
    return user.is_superuser or (hasattr(user, "profile") and user.profile.role in ("company_admin", "superadmin"))


@login_required
def website_editor(request):
    """Tab-based CMS editor for the company website."""
    if not _is_editor(request.user):
        return redirect("/")

    site = _get_site_for_user(request.user)
    if site is None:
        return redirect("/")

    if request.method == "POST":
        site.site_title = request.POST.get("site_title", site.site_title)
        site.tagline = request.POST.get("tagline", "")
        site.theme = request.POST.get("theme", site.theme)
        site.hero_text = request.POST.get("hero_text", "")
        site.about_text = request.POST.get("about_text", "")
        site.contact_phone = request.POST.get("contact_phone", "")
        site.contact_email = request.POST.get("contact_email", "")
        site.contact_address = request.POST.get("contact_address", "")
        site.facebook_url = request.POST.get("facebook_url", "")
        site.instagram_url = request.POST.get("instagram_url", "")
        site.primary_color = request.POST.get("primary_color", site.primary_color)
        site.is_published = "is_published" in request.POST
        if "logo" in request.FILES:
            site.logo = request.FILES["logo"]
        if "hero_image" in request.FILES:
            site.hero_image = request.FILES["hero_image"]
        site.save()
        messages.success(request, _("Web stranica uspjesno azurirana!"))
        return redirect("website:website_editor")

    unread = site.contact_messages.filter(is_read=False).count()
    return render(
        request,
        "website/editor.html",
        {
            "site": site,
            "services": site.services.all(),
            "gallery": site.gallery.all(),
            "reviews": site.reviews.all(),
            "messages_count": unread,
        },
    )


@login_required
def website_service_save(request):
    """Create or update a WebsiteService (AJAX POST)."""
    from .models import WebsiteService

    if not _is_editor(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    site = _get_site_for_user(request.user)
    if site is None:
        return JsonResponse({"ok": False, "error": "No site"}, status=400)

    pk = request.POST.get("pk")
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    icon = request.POST.get("icon", "").strip()
    price = request.POST.get("price_display", "").strip()
    order = int(request.POST.get("order", 0) or 0)
    is_active = request.POST.get("is_active", "1") == "1"

    if not title:
        return JsonResponse({"ok": False, "error": "Naziv je obavezan"}, status=400)

    if pk:
        try:
            svc = WebsiteService.objects.get(pk=pk, website=site)
        except WebsiteService.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Not found"}, status=404)
    else:
        svc = WebsiteService(website=site)

    svc.title = title
    svc.description = description
    svc.icon = icon
    svc.price_display = price
    svc.order = order
    svc.is_active = is_active
    svc.save()
    return JsonResponse({"ok": True, "pk": svc.pk, "title": svc.title})


@login_required
def website_service_delete(request, pk):
    """Delete a WebsiteService."""
    from .models import WebsiteService

    if not _is_editor(request.user):
        return JsonResponse({"ok": False}, status=403)
    site = _get_site_for_user(request.user)
    if site is None:
        return JsonResponse({"ok": False}, status=400)
    try:
        svc = WebsiteService.objects.get(pk=pk, website=site)
        svc.delete()
        return JsonResponse({"ok": True})
    except WebsiteService.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)


@login_required
def website_gallery_upload(request):
    """Upload a gallery image (AJAX POST)."""
    from .models import WebsiteGalleryImage

    if not _is_editor(request.user):
        return JsonResponse({"ok": False}, status=403)
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    site = _get_site_for_user(request.user)
    if site is None:
        return JsonResponse({"ok": False}, status=400)
    img_file = request.FILES.get("image")
    if not img_file:
        return JsonResponse({"ok": False, "error": "No image"}, status=400)
    caption = request.POST.get("caption", "").strip()
    obj = WebsiteGalleryImage.objects.create(
        website=site,
        image=img_file,
        caption=caption,
        is_active=True,
    )
    return JsonResponse({"ok": True, "pk": obj.pk, "url": obj.image.url})


@login_required
def website_gallery_delete(request, pk):
    """Delete a gallery image."""
    from .models import WebsiteGalleryImage

    if not _is_editor(request.user):
        return JsonResponse({"ok": False}, status=403)
    site = _get_site_for_user(request.user)
    if site is None:
        return JsonResponse({"ok": False}, status=400)
    try:
        obj = WebsiteGalleryImage.objects.get(pk=pk, website=site)
        obj.image.delete(save=False)
        obj.delete()
        return JsonResponse({"ok": True})
    except WebsiteGalleryImage.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)


@login_required
def website_review_save(request):
    """Create or update a WebsiteReview (AJAX POST)."""
    from .models import WebsiteReview

    if not _is_editor(request.user):
        return JsonResponse({"ok": False}, status=403)
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    site = _get_site_for_user(request.user)
    if site is None:
        return JsonResponse({"ok": False}, status=400)

    pk = request.POST.get("pk")
    author_name = request.POST.get("author_name", "").strip()
    rating = int(request.POST.get("rating", 5) or 5)
    text = request.POST.get("text", "").strip()
    is_approved = request.POST.get("is_approved", "1") == "1"

    if not author_name or not text:
        return JsonResponse({"ok": False, "error": "Ime i tekst su obavezni"}, status=400)

    if pk:
        try:
            rev = WebsiteReview.objects.get(pk=pk, website=site)
        except WebsiteReview.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Not found"}, status=404)
    else:
        rev = WebsiteReview(website=site)

    rev.author_name = author_name
    rev.rating = max(1, min(5, rating))
    rev.text = text
    rev.is_approved = is_approved
    rev.save()
    return JsonResponse({"ok": True, "pk": rev.pk})


@login_required
def website_messages(request):
    """Inbox for contact messages sent via public company site."""
    if not _is_editor(request.user):
        return redirect("/")
    site = _get_site_for_user(request.user)
    if site is None:
        return redirect("/")
    msgs = site.contact_messages.all()
    # Mark all as read
    site.contact_messages.filter(is_read=False).update(is_read=True)
    return render(
        request,
        "website/messages.html",
        {
            "site": site,
            "messages": msgs,
        },
    )
