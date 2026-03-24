from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .forms import HitnaIntervencijaForm
from .models import Brand, GalleryImage, HitnaIntervencija, VideoGallery


def homepage(request):
    """Javna web stranica (viskovic_group_index.html)"""
    return render(request, "viskovic_group_index.html")


def hitna_intervencija(request):
    """Javna forma za hitnu intervenciju"""
    if request.method == 'POST':
        form = HitnaIntervencijaForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            # Spremi IP adresu
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                obj.ip_adresa = x_forwarded_for.split(',')[0].strip()
            else:
                obj.ip_adresa = request.META.get('REMOTE_ADDR')
            # Jezik iz Accept-Language headera
            lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'de')
            obj.jezik = lang[:2].lower()
            obj.save()

            # Slanje email notifikacije (ako postoji email backend)
            try:
                from django.conf import settings

                from core.email_tasks import send_email_task
                subject = f"[HITNO] Nova intervencija: {obj.get_vrsta_display()} — {obj.ime}"
                body = (
                    f"Novi zahtjev za hitnu intervenciju\n\n"
                    f"Ime: {obj.ime}\n"
                    f"Telefon: {obj.telefon}\n"
                    f"Email: {obj.email}\n"
                    f"Adresa: {obj.adresa}, {obj.grad} ({obj.drzava})\n"
                    f"Vrsta: {obj.get_vrsta_display()}\n"
                    f"Hitnost: {'HITNO' if obj.hitnost else 'Redovito'}\n\n"
                    f"Opis:\n{obj.opis}\n"
                )
                notify_email = getattr(settings, 'HITNA_NOTIFY_EMAIL', None)
                if notify_email:
                    send_email_task.delay(subject, body, settings.DEFAULT_FROM_EMAIL, [notify_email])
            except Exception:
                pass

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'id': obj.id})
            messages.success(request, _('Vaš zahtjev je zaprimljen. Kontaktirat ćemo vas u najkraćem roku.'))
            return redirect('website:hitna_hvala')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    else:
        form = HitnaIntervencijaForm()

    return render(request, 'website/hitna_intervencija.html', {'form': form})


def hitna_hvala(request):
    """Stranica zahvale nakon slanja forme"""
    return render(request, 'website/hitna_hvala.html')


def video_galerija(request):
    """Javna video galerija"""
    kategorija = request.GET.get('k', '')
    videos = VideoGallery.objects.select_related("website").filter(is_active=True)
    if kategorija:
        videos = videos.filter(kategorija=kategorija)
    kategorije = VideoGallery.KATEGORIJA_CHOICES
    return render(request, 'website/video_galerija.html', {
        'videos': videos,
        'kategorije': kategorije,
        'aktivna_kategorija': kategorija,
    })


@login_required
def admin_panel(request):
    """Admin panel za upravljanje web stranicom"""
    brands    = Brand.objects.filter(is_active=True)
    gallery   = GalleryImage.objects.select_related("website").filter(is_active=True)
    hitne     = HitnaIntervencija.objects.filter(status='novo')[:10]
    videos    = VideoGallery.objects.select_related("website").filter(is_active=True)[:10]
    return render(request, 'website/index.html', {
        'brands': brands,
        'gallery': gallery,
        'hitne': hitne,
        'videos': videos,
    })


def viskovic_hr(request):
    from django.shortcuts import render
    return render(request, 'viskovic_group_index_hr.html')


def bau_page(request):
    from django.shortcuts import render

    from website.models import GalleryImage, VideoGallery
    media_items = []
    try:
        # Prikupi slike i filtriraj na razini Pythona
        for s in GalleryImage.objects.select_related("website").filter(is_active=True):
            cat = str(getattr(s, 'category', getattr(s, 'kategorija', ''))).lower()
            if 'bau' in cat or 'viskovi' in cat:
                if s.image:
                    title = getattr(s, 'caption_de', getattr(s, 'caption_hr', getattr(s, 'title', 'Referenz')))
                    media_items.append({'type': 'image', 'url': s.image.url, 'title': title})

        # Prikupi videe i filtriraj
        for v in VideoGallery.objects.select_related("website").filter(is_active=True):
            cat = str(getattr(v, 'kategorija', getattr(v, 'category', ''))).lower()
            if 'bau' in cat or 'viskovi' in cat:
                if getattr(v, 'video_file', None):
                    title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', getattr(v, 'title', 'Video')))
                    media_items.append({'type': 'video_file', 'url': v.video_file.url, 'title': title})
                elif getattr(v, 'embed_url', None):
                    title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', getattr(v, 'title', 'Video')))
                    media_items.append({'type': 'video_embed', 'url': v.embed_url, 'title': title})
    except Exception as e:
        print("Galerija Error:", e)
    return render(request, 'website/bau.html', {'media_items': media_items})



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MULTI-TENANT WEBSITE BUILDER — PUBLIC VIEWS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def company_site(request, slug):
    """Public company website page."""
    from django.shortcuts import get_object_or_404

    from .models import CompanyWebsite
    site = get_object_or_404(CompanyWebsite, slug=slug, is_published=True)
    services = site.services.filter(is_active=True)
    gallery  = site.gallery.filter(is_active=True)
    reviews  = site.reviews.filter(is_approved=True)
    return render(request, f'website/themes/{site.theme}.html', {
        'site':     site,
        'services': services,
        'gallery':  gallery,
        'reviews':  reviews,
    })


@require_POST
def company_site_contact(request, slug):
    """Handle contact form submission from public company site."""
    from django.shortcuts import get_object_or_404

    from .models import CompanyWebsite, WebsiteContactMessage
    site = get_object_or_404(CompanyWebsite, slug=slug, is_published=True)
    name    = request.POST.get('name', '').strip()
    email   = request.POST.get('email', '').strip()
    phone   = request.POST.get('phone', '').strip()
    msg     = request.POST.get('message', '').strip()
    if not name or not email or not msg:
        messages.error(request, _('Molimo ispunite sva obavezna polja.'))
        return redirect(f'/site/{slug}/#contact')
    WebsiteContactMessage.objects.create(
        website=site, name=name, email=email, phone=phone, message=msg,
    )
    messages.success(request, _('Vasa poruka je uspjesno poslana!'))
    return redirect(f'/site/{slug}/#contact')

# --- Grosmarkt partner API -------------------------------------------

GROSMARKT_TOTAL_SLOTS = 5

ROLE_ICONS = {
    'logistik':   {'icon': 'fas fa-warehouse',   'color': '#c9a84c'},
    'gaertnerei': {'icon': 'fas fa-leaf',         'color': '#22c55e'},
    'haendler':   {'icon': 'fas fa-store',        'color': '#3b82f6'},
    'gastro':     {'icon': 'fas fa-utensils',     'color': '#f97316'},
    'sonstiges':  {'icon': 'fas fa-building',     'color': '#94a3b8'},
}

ROLE_LABELS = {
    'logistik':   'Logistik-Hub',
    'gaertnerei': 'Gärtnerei & Frischware',
    'haendler':   'Händler & Großhandel',
    'gastro':     'Gastronomie',
    'sonstiges':  'Partner',
}


@require_GET
def grosmarkt_partners_api(request):
    """Public JSON endpoint for grosmarkt-online.eu partner cards."""
    from companies.models import Company

    partners = Company.objects.filter(
        grosmarkt_partner=True
    ).values(
        'name', 'city', 'grosmarkt_role',
        'grosmarkt_description', 'grosmarkt_show_name',
        'website_url',
    ).order_by('created_at')

    data = []
    for p in partners:
        role = p['grosmarkt_role'] or 'sonstiges'
        style = ROLE_ICONS.get(role, ROLE_ICONS['sonstiges'])
        data.append({
            'name':        p['name'] if p['grosmarkt_show_name'] else None,
            'city':        p['city'] if p['grosmarkt_show_name'] else None,
            'role':        role,
            'role_label':  ROLE_LABELS.get(role, 'Partner'),
            'description': p['grosmarkt_description'],
            'icon':        style['icon'],
            'color':       style['color'],
            'website':     p['website_url'] if p['grosmarkt_show_name'] else None,
        })

    return JsonResponse({
        'partners':    data,
        'total_slots': GROSMARKT_TOTAL_SLOTS,
        'taken_slots': len(data),
        'open_slots':  GROSMARKT_TOTAL_SLOTS - len(data),
    }, json_dumps_params={'ensure_ascii': False})



import json as _json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST as _require_POST

@csrf_exempt
@_require_POST
def grosmarkt_anfrage(request):
    """
    POST endpoint za demo-anfrage s grosmarkt-online.eu.
    CORS je riješen nginx-om za grosmarkt-online.eu.
    Sprema u bazu + šalje email na viskovic.bau@gmail.com.
    """
    from django.http import JsonResponse
    from django.conf import settings
    from django.utils.timezone import now
    from .models import GrosmarktAnfrage
    from core.email_tasks import send_html_email_task

    try:
        # Prihvati i JSON i form-data
        if request.content_type and "application/json" in request.content_type:
            try:
                body = _json.loads(request.body)
            except Exception:
                body = {}
        else:
            body = request.POST

        name    = str(body.get("name", "")).strip()[:200]
        company = str(body.get("company", "")).strip()[:200]
        email   = str(body.get("email", "")).strip()[:254]
        phone   = str(body.get("phone", "")).strip()[:50]
        message = str(body.get("message", "")).strip()[:2000]

        # Validacija
        errors = {}
        if not name:    errors["name"]    = "Name ist erforderlich."
        if not company: errors["company"] = "Unternehmen ist erforderlich."
        if not email or "@" not in email:
            errors["email"] = "Gültige E-Mail ist erforderlich."
        if errors:
            return JsonResponse({"success": False, "errors": errors}, status=400)

        # Spremi u bazu
        anfrage = GrosmarktAnfrage.objects.create(
            name=name, company=company, email=email,
            phone=phone, message=message,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )

        # Email na viskovic.bau@gmail.com
        notify_email = getattr(settings, "HITNA_NOTIFY_EMAIL", "viskovic.bau@gmail.com")
        subject = f"[Grosmarkt] Neue Anfrage — {company}"

        text_body = (
            f"NEUE DEMO-ANFRAGE — grosmarkt-online.eu\n"
            f"{'='*50}\n"
            f"Firma:    {company}\n"
            f"Name:     {name}\n"
            f"E-Mail:   {email}\n"
            f"Telefon:  {phone or '—'}\n"
            f"Nachricht:\n{message or '—'}\n"
            f"{'='*50}\n"
            f"Eingegangen: {now().strftime('%d.%m.%Y %H:%M')}\n"
            f"Admin: https://limit-connect.com/admin/website/grosmarktanfrage/{anfrage.pk}/change/"
        )

        html_body = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0a0a0a;color:#e2e8f0;padding:32px;border-radius:12px;">
          <div style="border-left:4px solid #c9a84c;padding-left:16px;margin-bottom:24px;">
            <h2 style="color:#c9a84c;margin:0 0 4px;">Neue Demo-Anfrage</h2>
            <p style="color:#94a3b8;margin:0;font-size:0.85rem;">grosmarkt-online.eu</p>
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:10px 0;color:#94a3b8;width:120px;">Firma</td>
                <td style="padding:10px 0;font-weight:700;color:#fff;">{company}</td></tr>
            <tr><td style="padding:10px 0;color:#94a3b8;">Name</td>
                <td style="padding:10px 0;color:#fff;">{name}</td></tr>
            <tr><td style="padding:10px 0;color:#94a3b8;">E-Mail</td>
                <td style="padding:10px 0;"><a href="mailto:{email}" style="color:#c9a84c;">{email}</a></td></tr>
            <tr><td style="padding:10px 0;color:#94a3b8;">Telefon</td>
                <td style="padding:10px 0;color:#fff;">{phone or "—"}</td></tr>
            {"<tr><td style='padding:10px 0;color:#94a3b8;vertical-align:top;'>Nachricht</td><td style='padding:10px 0;color:#fff;'>" + message + "</td></tr>" if message else ""}
          </table>
          <div style="margin-top:24px;padding-top:24px;border-top:1px solid #333;">
            <a href="https://limit-connect.com/admin/website/grosmarktanfrage/{anfrage.pk}/change/"
               style="background:#c9a84c;color:#000;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;">
              In Admin öffnen →
            </a>
          </div>
        </div>
        """

        try:
            send_html_email_task.delay(
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                from_email=None,
                recipient_list=[notify_email],
            )
        except Exception:
            # Celery možda ne radi — pokušaj sync
            from django.core.mail import send_mail
            send_mail(subject, text_body, None, [notify_email], fail_silently=True)

        # Auto-reply podnositelju
        auto_reply_subject = "Danke für Ihre Anfrage — Grosmarkt Online"
        auto_reply_text = (
            f"Guten Tag {name},\n\n"
            f"vielen Dank für Ihr Interesse an Grosmarkt Online.\n"
            f"Wir melden uns innerhalb von 24 Stunden für eine persönliche Demo.\n\n"
            f"Mit freundlichen Grüßen\n"
            f"Ivan Viskovic\n"
            f"Grosmarkt Online | viskovic-group.de"
        )
        try:
            send_html_email_task.delay(
                subject=auto_reply_subject,
                text_body=auto_reply_text,
                html_body=f"<p style='font-family:sans-serif'>{auto_reply_text.replace(chr(10),'<br>')}</p>",
                from_email=None,
                recipient_list=[email],
            )
        except Exception:
            pass

        return JsonResponse({
            "success": True,
            "message": "Anfrage erfolgreich eingegangen.",
            "id": anfrage.pk,
        })

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("grosmarkt_anfrage error")
        return JsonResponse({"success": False, "error": "Serverfehler. Bitte später erneut versuchen."}, status=500)


def pricing_page(request):
    """Public pricing page for limit-connect.com."""
    from registration.models import PricingPlan
    from registration.constants import PLAN_FEATURES
    plans = PricingPlan.objects.filter(is_active=True).order_by('sort_order')
    lang = request.GET.get('lang', 'hr')
    return render(request, 'website/pricing.html', {
        'plans': plans,
        'plan_features': PLAN_FEATURES,
        'lang': lang,
    })


def pricing_ai_advisor(request):
    """AI-powered plan recommendation based on business description."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    import json
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}

    industry = body.get('industry', '')
    employees = int(body.get('employees', 1))
    needs = body.get('needs', [])

    score = {'starter': 0, 'professional': 0, 'enterprise': 0}

    if employees <= 3:
        score['starter'] += 3
    elif employees <= 15:
        score['professional'] += 3
    else:
        score['enterprise'] += 3

    enterprise_needs = {'inventory', 'ai', 'eracun', 'rental', 'webshop', 'synesis', 'smart_import', 'helpdesk'}
    pro_needs = {'tracking', 'reports', 'konto', 'payroll', 'delivery', 'marketplace', 'gastro'}

    for n in needs:
        if n in enterprise_needs:
            score['enterprise'] += 2
        elif n in pro_needs:
            score['professional'] += 2
        else:
            score['starter'] += 1

    if industry in ('gastro', 'trade', 'construction'):
        score['professional'] += 1
    if industry in ('health', 'it'):
        score['enterprise'] += 1

    recommended = max(score, key=score.get)
    reasons = {
        'starter': 'Za male tvrtke do 3 korisnika s osnovnim potrebama fakturiranja i POS-a.',
        'professional': 'Idealan za rastuce tvrtke koje trebaju izvjestaje, tracking, payroll i CRM.',
        'enterprise': 'Kompletno rjesenje sa svim modulima, AI asistentom i neogranicenim korisnicima.',
    }

    return JsonResponse({
        'recommended': recommended,
        'reason': reasons[recommended],
        'scores': score,
    })


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from core.company_utils import get_user_company

@login_required
def gallery_manage(request):
    """Upload i upravljanje slikama za web stranicu firme."""
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Nema aktivne firme.')
        return redirect('/')

    from website.models import GalleryImage
    images = GalleryImage.objects.filter(company=company).order_by('category', 'sort_order')
    return render(request, 'website/gallery_manage.html', {
        'images': images,
        'company': company,
        'categories': GalleryImage.CATEGORY,
    })

@login_required
def gallery_upload(request):
    """AJAX upload slike."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    company = get_user_company(request)
    if not company:
        return JsonResponse({'error': 'Nema firme'}, status=400)

    files = request.FILES.getlist('images')
    category = request.POST.get('category', 'product')
    if not files:
        return JsonResponse({'error': 'Nema slika'}, status=400)

    from website.models import GalleryImage
    created = []
    for f in files:
        if not f.content_type.startswith('image/'):
            continue
        if f.size > 10 * 1024 * 1024:
            continue
        img = GalleryImage.objects.create(
            company=company,
            image=f,
            title=f.name.rsplit('.', 1)[0][:100],
            category=category,
            uploaded_by=request.user,
        )
        created.append({'id': img.pk, 'url': img.image.url, 'title': img.title})

    return JsonResponse({'ok': True, 'count': len(created), 'images': created})

@login_required
def gallery_delete(request, pk):
    """Obriši sliku."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    company = get_user_company(request)
    from website.models import GalleryImage
    try:
        img = GalleryImage.objects.get(pk=pk, company=company)
        img.delete()
        return JsonResponse({'ok': True})
    except GalleryImage.DoesNotExist:
        return JsonResponse({'error': 'Ne postoji'}, status=404)


def feedback_page(request):
    """Public feedback stranica — limit-connect.com/feedback/"""
    return render(request, 'website/feedback.html')


def digitalni_posrednik(request):
    """Javna stranica: Digitalni Posrednik — kronologija i upute."""
    return render(request, 'website/digitalni_posrednik.html')


def digitalni_posrednik(request):
    """Public page: Digitalni Posrednik chronicle and status."""
    return render(request, 'website/digitalni_posrednik.html')
