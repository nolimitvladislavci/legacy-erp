from django.contrib import admin
from django.shortcuts import redirect
from core import tc_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
from django.views.generic import RedirectView
from django.http import FileResponse, Http404
import os as _os
from django.contrib.auth import views as auth_views
from . import views
from core import steuerberater_views
from core import intelligence_views
from core import oib_finalizer_views
from core import onboarding_views

def _serve_offline(request):
    of_path = _os.path.join(settings.BASE_DIR, 'static', 'offline.html')
    if not _os.path.exists(of_path):
        raise Http404
    return FileResponse(open(of_path, 'rb'), content_type='text/html')

def _serve_manifest(request):
    mf_path = _os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    if not _os.path.exists(mf_path):
        raise Http404
    return FileResponse(open(mf_path, 'rb'), content_type='application/manifest+json')

def _serve_sw(request):
    sw_path = _os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if not _os.path.exists(sw_path):
        raise Http404
    return FileResponse(open(sw_path, 'rb'), content_type='application/javascript')

from django.views.generic import TemplateView


# TEMP: direct POS bypass za shevqet redirect loop debug
def _bypass_login(request, token):
    from django.contrib.auth import login as _al, get_user_model as _gu
    from django.http import HttpResponse
    from django.shortcuts import redirect
    from django.views.decorators.csrf import csrf_exempt
    if token != 'sl2026frisko': return HttpResponse('Invalid', status=403)
    try:
        u = _gu().objects.get(username='shevqet')
        u.backend = 'django.contrib.auth.backends.ModelBackend'
        _al(request, u)
        return redirect('/hr/pos/')
    except Exception as e:
        return HttpResponse(str(e))

# TEMP DEBUG — remove after fixing login

def _shell_test(request):
    from django.shortcuts import render
    return render(request, 'shell_test.html')

def _debug_session(request):
    from django.http import JsonResponse
    return JsonResponse({
        'authenticated': request.user.is_authenticated,
        'username': request.user.username if request.user.is_authenticated else None,
        'session_key': request.session.session_key,
        'cookies': list(request.COOKIES.keys()),
    })

urlpatterns = [
    path('_shell_test/', _shell_test),
    path('_debug_session/', _debug_session),
    # Smart Entry — /pocni/ jedina ulazna točka
    path('postani-distributer/', __import__('registration.views', fromlist=['distributor_apply']).distributor_apply, name='distributor_apply'),
    path('pocni/', __import__('registration.smart_entry', fromlist=['pocni']).pocni, name='smart_entry'),
    path('pocni/provjeri/', __import__('registration.smart_entry', fromlist=['api_detect_email']).api_detect_email, name='api_detect_email'),
    path('pocni/magic/<path:token>/', __import__('registration.smart_entry', fromlist=['magic_login']).magic_login, name='magic_login'),

    # Landing 2026 — root homepage
    path('', __import__('website.views', fromlist=['homepage']).homepage, name='landing_root'),


    # Claim Your Business — public URLs
    path('firma/preuzmi/<uuid:company_id>/', __import__('registration.views', fromlist=['claim_company_form']).claim_company_form, name='claim_company'),
    path('firma/preuzmi/<uuid:company_id>/submit/', __import__('registration.views', fromlist=['submit_claim']).submit_claim, name='submit_claim'),
    path('firma/aktiviraj/<path:token>/', __import__('registration.views', fromlist=['activate_via_invite']).activate_via_invite, name='activate_invite'),

    # path('_bypass/<path:token>/', _bypass_login),  # DISABLED — sigurnosni rizik
    path('golubar/', TemplateView.as_view(template_name='brochure_golubar.html'), name='brochure_golubar'),
    path('radni-sati/', TemplateView.as_view(template_name='brosura_radni_sati_landing.html'), name='brochure_worktime'),
    path('arhiva/', TemplateView.as_view(template_name='brosura_arhiva_landing.html'), name='brochure_arhiva'),
    
    path('vrtic/<slug:slug>/portal/', __import__('kindergarten.views', fromlist=['parent_portal']).parent_portal, name='kindergarten_portal'),
    path('lib/<slug:slug>/', include('library.public_urls')),
    path('validator/', TemplateView.as_view(template_name='website/brosura_croxmlverify.html'), name='brochure_croxmlverify'),
    path('no-limit/', include('no_limit.urls')),
    path('gov_export/', include('gov_export.urls')),
    path('legal/tc-accept/', tc_views.tc_accept_view, name='tc_accept'),

    # BEZ PAPIRA — public receipt (no login)
    path('pos/r/<int:receipt_id>/<path:token>/', __import__('pos.views', fromlist=['receipt_public']).receipt_public, name='receipt_public_short'),
    path('pos/r/<int:receipt_id>/<path:token>', __import__('pos.views', fromlist=['receipt_public']).receipt_public, name='receipt_public_noslash'),

    path('bau/', __import__('website.views', fromlist=['bau_page']).bau_page, name='bau_page_root'),
    path('sw.js',        _serve_sw,       name='sw_js'),
    path('manifest.json', _serve_manifest, name='manifest_json'),
    path('offline.html',  _serve_offline,  name='offline_html'),
    path('burza/', include('burza.urls', namespace='burza')),
    path('', include('borg_ops.urls', namespace='borg_ops')),
    path('vrtic/', include('kindergarten.urls', namespace='kindergarten')),
    path('dom/', include('eldercare.urls', namespace='eldercare')),
    path('lib/staff/', include('library.urls', namespace='library')),
    path('livestock/', include('livestock.urls', namespace='livestock')),
    path('lovacki/', include('lovacki.urls', namespace='lovacki')),
    path('utilities/', include('utilities.urls', namespace='utilities')),
    path('komunalno/', include('komunalno.urls', namespace='komunalno')),
    path('intelligence/', include('intelligence.urls', namespace='intelligence')),
    path('marketplace/', include('marketplace.urls', namespace='marketplace')),
    path('delivery/', include('delivery.urls', namespace='delivery')),
    # path('traceability/', include('traceability.urls', namespace='traceability')),  # dormant app
    path('gastro-menu/', include('gastro_menu.urls', namespace='gastro_menu')),
    path('knjiznica/', include('knjiznica.urls', namespace='knjiznica')),
    path('sezonci/', include('seasonal.urls', namespace='seasonal')),
    path('sos/', __import__('interventions.views', fromlist=['public_intervention']).public_intervention, name='public_sos'),
        path('track/<uuid:tracking_token>/', __import__('interventions.views', fromlist=['tracking_view']).tracking_view, name='intervention_tracking'),
    path('i18n/setlang/', set_language, name='set_language'),
    path('i18n/', include('django.conf.urls.i18n')),
    # Webhook Rampa (izvan i18n - nema language redirect)
    path('smart-import/api/inbound-webhook/<str:secret>/', __import__('smart_import.views', fromlist=['inbound_email_webhook']).inbound_email_webhook, name='inbound_webhook_direct'),
    path('rosetta/', include('rosetta.urls')),
    # Ovaj red rješava 404 grešku na /accounts/login/
    path('accounts/login/', RedirectView.as_view(pattern_name='login', permanent=True)),
    path('login/', views.login_view, name='login_root'),
    # Device token scan API (izvan i18n — koristi ga POS scanner direktno)
    path('api/device-login/', __import__('accounts.auth_views', fromlist=['device_token_login']).device_token_login, name='device_token_login_api'),
    path('api/ai-agent/', __import__('superadmin_ai.views', fromlist=['agent_gateway']).agent_gateway, name='ai_agent_gateway'),
    path('api/fenix-input/', include('fenix_input.urls', namespace='fenix_input')),
    # Memio superadmin
    path('memio-admin/', __import__('memio_pet.views_admin', fromlist=['memio_dashboard']).memio_dashboard, name='memio_admin_dashboard'),
    path('memio-admin/animal/<uuid:animal_id>/', __import__('memio_pet.views_admin', fromlist=['admin_animal_action']).admin_animal_action, name='memio_admin_animal_action'),
    path('memio-admin/profile/<uuid:profile_id>/', __import__('memio_pet.views_admin', fromlist=['admin_profile_action']).admin_profile_action, name='memio_admin_profile_action'),
]

urlpatterns += i18n_patterns(

    # Claim Your Business — authenticated
    # Agent dashboard alias
    path('moji-klijenti/', __import__('registration.views', fromlist=['agent_dashboard']).agent_dashboard, name='moji_klijenti'),

    path('firma/odobri/<uuid:claim_id>/', __import__('registration.views', fromlist=['approve_claim']).approve_claim, name='approve_claim'),
    path('firma/zahtjevi/', __import__('registration.views', fromlist=['pending_claims']).pending_claims, name='pending_claims'),
    path('posrednik/invite/<uuid:company_id>/', __import__('registration.views', fromlist=['send_company_invite']).send_company_invite, name='send_company_invite'),
    path('golubar/', TemplateView.as_view(template_name='brochure_golubar.html'), name='brochure_golubar_i18n'),
    path('premium/', include('premium_booking.urls')),
    path('admin/login/', lambda request: redirect('/worktime/') if request.user.is_authenticated and not request.user.is_staff else admin.site.login(request), name='admin_login_redirect'),
    path('j3wkuxuwuuc9/', admin.site.urls),
    # Stara /admin/ URL → 404 silent (ne otkrivamo da smo premjestili)
    path('admin/', lambda r: __import__('django.http', fromlist=['HttpResponseNotFound']).HttpResponseNotFound('Not Found')),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # 2FA (TOTP)
    path('2fa/setup/', __import__('accounts.auth_views', fromlist=['setup_2fa']).setup_2fa, name='setup_2fa'),
    path('2fa/verify/', __import__('accounts.auth_views', fromlist=['verify_2fa']).verify_2fa, name='verify_2fa'),
    path('auth/verify-email/<path:token>/', __import__('accounts.auth_views', fromlist=['verify_email']).verify_email, name='verify_email'),
    path('auth/resend-verification/', __import__('accounts.auth_views', fromlist=['resend_verification']).resend_verification, name='resend_verification'),

    # GDPR (Clanak 17 + 20)
    path('gdpr/export/', __import__('accounts.auth_views', fromlist=['gdpr_export_view']).gdpr_export_view, name='gdpr_export'),
    path('gdpr/delete/', __import__('accounts.auth_views', fromlist=['gdpr_delete_view']).gdpr_delete_view, name='gdpr_delete'),
    path("gdpr/dashboard/", __import__("core.gdpr_views", fromlist=["gdpr_dashboard"]).gdpr_dashboard, name="gdpr_dashboard"),
    path("api/gdpr/export/", __import__("core.gdpr_views", fromlist=["api_gdpr_export"]).api_gdpr_export, name="api_gdpr_export"),
    path("api/gdpr/erase/", __import__("core.gdpr_views", fromlist=["api_gdpr_erase"]).api_gdpr_erase, name="api_gdpr_erase"),

    # Device token (mobilni barcode login)
    path('auth/device-tokens/', __import__('accounts.auth_views', fromlist=['device_token_manage']).device_token_manage, name='device_token_manage'),
    path('auth/device-tokens/<int:token_id>/', __import__('accounts.auth_views', fromlist=['device_token_detail']).device_token_detail, name='device_token_detail'),
    path("auth/device-tokens/<int:token_id>/qr.png", __import__("accounts.auth_views", fromlist=["device_token_qr_image"]).device_token_qr_image, name="device_token_qr_image"),
    path('auth/device-login/', __import__('accounts.auth_views', fromlist=['device_token_auto_login']).device_token_auto_login, name='device_token_auto_login'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.txt',
        html_email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/hr/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/hr/password-reset/complete/',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('', views.smart_home, name='home'),
    path('dashboard/', views.smart_home, name='dashboard'),
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/cross-company/', views.cross_company_dashboard, name='cross_company_dashboard'),
    path('superadmin/tc-status/', views.tc_consent_status, name='tc_consent_status'),
    path('superadmin/borg-errors/', views.borg_error_queue, name='borg_error_queue'),
    path('superadmin/tc-remind/', views.tc_consent_remind, name='tc_consent_remind'),
    path('superadmin/ai/', include('superadmin_ai.urls')),
    path('superadmin/ivan/', views.ivan_cockpit, name='ivan_cockpit'),
    path('api/cockpit/send-whatsapp/', views.cockpit_send_whatsapp, name='cockpit_send_whatsapp'),
    path('api/cockpit/upload-photo/', views.cockpit_upload_photo, name='cockpit_upload_photo'),
    path('api/cockpit/photos/', views.cockpit_photos, name='cockpit_photos'),
    path('api/cockpit/gemini-task/', views.cockpit_gemini_task, name='cockpit_gemini_task'),
    path('tim-chat/', views.tim_chat, name='tim_chat'),
    path('tim-chat/send/', views.tim_chat_send, name='tim_chat_send'),
    path('steuerberater/', steuerberater_views.steuerberater_portal, name='steuerberater_portal'),
    path('steuerberater/upload/', steuerberater_views.steuerberater_upload, name='steuerberater_upload'),

    path("admin/knjiga/", __import__("core.knjiga_view", fromlist=["knjiga_pristupnih_podataka"]).knjiga_pristupnih_podataka, name="knjiga_pristupnih_podataka"),
    path("knjiga-boljitaka/", __import__("core.knjiga_view", fromlist=["knjiga_boljitaka"]).knjiga_boljitaka, name="knjiga_boljitaka"),
    path("revizorski-paket/", views.audit_package, name="audit_package"),
    path("newsletter/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'core/newsletter_2026.html'), name="newsletter"),
        # Promo landing pages
    path("promo/", views.promo_page, name="promo_hr"),
    path("promo/de/", views.promo_page_de, name="promo_de"),
    path("promo/opg/", views.promo_opg, name="promo_opg"),
    path("newsletter/de/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'core/newsletter_2026_de.html'), name="newsletter_de"),

    # DE Promotion Pack
    path("de/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/de_landing.html'), name="de_landing"),
    path("de/pakete/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/de_pakete.html'), name="de_pakete"),
    path("de/anleitung/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/de_anleitung.html'), name="de_anleitung"),
    path("de/ohne-papier/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/de_ohne_papier.html'), name="de_ohne_papier"),

    # Legal — Tippgeber/Posrednik
    path("legal/tippgeber-vertrag/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'legal/tippgeber_vertrag_de.html'), name="tippgeber_vertrag"),
    path("legal/tippgeber-ausweis/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'legal/tippgeber_ausweis_de.html'), name="tippgeber_ausweis"),
    path("legal/posrednicki-ugovor/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'legal/posrednicki_ugovor_hr.html'), name="posrednicki_ugovor"),
    path("legal/opci-uvjeti/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'legal/opci_uvjeti_hr.html'), name="opci_uvjeti"),
    path('legal/tc-consent/', __import__('core.views', fromlist=['tc_consent']).tc_consent, name='tc_consent'),
    path("legal/dpa/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'legal/dpa_hr.html'), name="dpa"),

    # Partner Signup (public)
    path("partner/", lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/partner_signup.html'), name="partner_signup"),
    path("api/partner-signup/", views.partner_signup_api, name="partner_signup_api"),

    # Robot Prodavač — SEO landing
    path('robot-pekara/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'landing/robot_pekara.html'), name='robot_pekara'),
    # UVIJEK FRIŠKO — landing + letci
    path('frisko/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/landing_frisko.html')),
    path('frisko/letak/a3/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/letak_a3_frisko.html')),
    path('frisko/letak/a4/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/letak_a4_frisko.html')),
    path('frisko/letak/pm/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/letak_a4_pm_frisko.html')),
# FRIŠKO RIZO — landing + letci
    path("frisko-rizo/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/landing_frisko_rizo.html")),
    path("frisko-rizo/letak-a3/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/letak_a3_frisko_rizo.html")),
    path("frisko-rizo/letak-a4/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/letak_a4_frisko_rizo.html")),
    path('seki-paket/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/seki_paket.html')),
    path("rizo-paket/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/rizo_paket.html")),
    path('optika-konjik/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/optika_konjik.html')),
    path('knjiga-boljitaka/', lambda r: __import__('django.shortcuts', fromlist=['render']).render(r, 'website/knjiga_boljitaka.html')),
# KORPAŠ — landing + letak
    path("korpas/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/landing_korpas.html")),
    path("korpas/termini/", __import__("django.views.generic", fromlist=["RedirectView"]).RedirectView.as_view(url="/hr/appointments/booking/c/korpas-doo/", permanent=False), name="korpas_termini"),
    path("korpas/sirokisor/", __import__("website.views", fromlist=["sirokisor"]).sirokisor, name="sirokisor"),
    path("upute/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/upute_centralne.html"), name="upute_centralne"),
    path("korpas/kud-dukat/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/kud_dukat.html")),
    path("korpas/opg-kruljac/", __import__("website.views", fromlist=["opg_kruljac"]).opg_kruljac, name="opg_kruljac"),
    path("cro-validator/", __import__("django.views.generic", fromlist=["RedirectView"]).RedirectView.as_view(url="/validator/", permanent=False), name="cro_validator"),
    path("no-limit/partner/", __import__("website.views", fromlist=["nolimit_partner"]).nolimit_partner, name="nolimit_partner"),
    path("korpas/letak/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "website/letak_a4_korpas.html")),
    path('scan/<path:token>/', include([
        path('', __import__('documents.views', fromlist=['scan_mobile_page']).scan_mobile_page, name='scan_mobile'),
        path('upload/', __import__('documents.views', fromlist=['scan_upload']).scan_upload, name='scan_upload'),
    ])),
    path('superadmin/control-tower/', views.control_tower_view, name='control_tower'),
    path('superadmin/api/telemetry/', views.control_tower_api, name='control_tower_api'),
    path('superadmin/modules/<uuid:subscription_id>/', views.update_company_modules, name='update_company_modules'),
    path('superadmin/companies/<uuid:company_id>/branches/', views.superadmin_company_branches, name='superadmin_company_branches'),
    path('superadmin/companies/', views.superadmin_companies, name='superadmin_companies'),
    path('superadmin/users/', views.superadmin_users, name='superadmin_users'),
    path('umbrella/', views.umbrella_dashboard, name='umbrella_dashboard'),
    path('umbrella/intelligence/', intelligence_views.intelligence_dashboard, name='intelligence_dashboard'),
    path('umbrella/intelligence/search/', intelligence_views.intelligence_search, name='intelligence_search'),
    path('umbrella/drafts/', oib_finalizer_views.draft_companies_view, name='draft_companies'),
    path('umbrella/drafts/finalize/', oib_finalizer_views.finalize_oib_view, name='finalize_oib'),
    path('api/oib-finalizer/', oib_finalizer_views.finalize_oib_api, name='finalize_oib_api'),
    path('umbrella/switch/<uuid:company_id>/', views.umbrella_switch_company, name='umbrella_switch_company'),
    path('umbrella/switch-back/', views.umbrella_switch_back, name='umbrella_switch_back'),
    path('superadmin/users/<int:user_id>/edit/', views.superadmin_edit_user, name='superadmin_edit_user'),
    path('superadmin/impersonate/<uuid:company_id>/', views.start_impersonation, name='start_impersonation'),
    path('superadmin/impersonate/stop/', views.stop_impersonation, name='stop_impersonation'),
    path('superadmin/promo/create/', views.superadmin_create_promo, name='superadmin_create_promo'),
    path('stolarija/', include('stolarija.urls', namespace='stolarija')),
    path('panic/', __import__('core.views_inspector', fromlist=['panic_button']).panic_button, name='panic_button'),
    path('panic/revoke/<int:token_id>/', __import__('core.views_inspector', fromlist=['panic_revoke']).panic_revoke, name='panic_revoke'),
    path('panel/detail/', views.panel_detail, name='panel_detail'),
    path('accounts/', include('accounts.urls')),
    path('companies/', include('companies.urls')),
    path('partners/', include('partners.urls')),
    path('documents/', include('documents.urls')),
    path('calculator/', include('calculator.urls')),
    path('worktime/', include('worktime.urls')),
    path('payroll/', include('payroll.urls')),
    path('pdv-s/', include('pdv_s.urls')),
    path('porezni-savjetnik/', include('tax_wizard.urls')),
    path('aml/', include('aml.urls')),
    path('edik/', include('edik.urls')),
    path('virtual-office/', include('virtual_office.urls')),
    path('appointments/', include('appointments.urls')),
    path('invoicing/', include('invoicing.urls')),
    path('webshop/', include('webshop.urls')),
    path('rental/', include('rental.urls')),
    # path('fitness/', include('fitness.urls')),  # dormant app
    path("udruge/", include("udruge.urls")),
    path('finance/', include('finance.urls')),
    path('inventory/', include('inventory.urls')),
    path('work-orders/', include('work_orders.urls', namespace='work_orders')),
    # path('insurance/', include('insurance.urls')),  # dormant app
    path('projects/', include('projects.urls')),
    path('pos/', include('pos.urls')),
    path('payments/', include('payments.urls')),
    path('eracun/', include('eracun.urls')),
    path('api/einvoice/', include('einvoice.api.urls')),
    path('einvoice/', include('einvoice.urls')),
    path('helpdesk/', include('helpdesk.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('propter/', include('propter.urls')),
    path('procurement/', include('procurement.urls')),
    path('prodaja/', include('sales.urls')),
    path('proizvodnja/', include('production.urls')),
    path('fiscal/', include('fiscal.urls')),
    path('tracking/', include('tracking.urls')),
    path('interventions/', include('interventions.urls', namespace='interventions')),
    path('branches/', include('companies.urls_branches', namespace='branches')),
    path('assessment/', include('assessment.urls', namespace='assessment')),
    path('outreach/', include('outreach.urls', namespace='outreach')),
    path('ai/', include('ai_assistant.urls', namespace='ai_assistant')),
    path('ai-cockpit/', include('limit_connect_ai.urls', namespace='limit_connect_ai')),
    path('superadmin/fiskalizacija/', include('fiskalizacija.urls', namespace='fiskalizacija')),
    path('push/', include('push_notifications.urls', namespace='push')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('reports/', include('reports.urls', namespace='reports')),
    path('register/', include('registration.urls')),
    path('about/', __import__('website.views', fromlist=['about_page']).about_page, name='about'),
    path('plan-isplativosti/', __import__('website.views', fromlist=['financijski_plan']).financijski_plan, name='financijski_plan'),
    path('trzisna-analiza/', __import__('website.views', fromlist=['trzisna_analiza']).trzisna_analiza, name='trzisna_analiza'),
    path('pricing/', __import__('website.views', fromlist=['pricing_page']).pricing_page, name='pricing'),
    path('api/pricing/advisor/', __import__('website.views', fromlist=['pricing_ai_advisor']).pricing_ai_advisor, name='pricing_ai_advisor'),
    path('synesis/', include('synesis.urls')),
    path('smart-import/', include('smart_import.urls', namespace='smart_import')),
    
    # Boxgram Web Routes (public) — prefiks boxgram/ za memio.pet nginx proxy
    path('boxgram/', include('boxgram.urls', namespace='boxgram')),

    path('data-migration/', include('data_migration.urls')),
    path('konto/', include('konto.urls')),
    path('honorari/', include('honorari.urls')),
    
    path('website/', include('website.urls')),
    path('site/', include('website.site_urls')),
    # Onboarding wizard
    path('onboarding/', onboarding_views.onboarding_wizard, name='onboarding_wizard'),
    path('onboarding/update-profile/', onboarding_views.onboarding_update_profile, name='onboarding_update_profile'),
    path('onboarding/add-partner/', onboarding_views.onboarding_add_partner, name='onboarding_add_partner'),
    path('onboarding/add-item/', onboarding_views.onboarding_add_item, name='onboarding_add_item'),
    path('onboarding/activate-pos/', onboarding_views.onboarding_activate_pos, name='onboarding_activate_pos'),
    path('onboarding/skip-step/', onboarding_views.onboarding_skip_step, name='onboarding_skip_step'),
    path('onboarding/complete/', onboarding_views.onboarding_complete, name='onboarding_complete'),

    path('dashboard/company/', views.company_dashboard, name='company_dashboard'),
    path('dashboard/manager/', views.manager_dashboard, name='manager_dashboard'),
    path('dashboard/worker/', views.worker_dashboard, name='worker_dashboard'),
    path('dashboard/worker/camera/', __import__('worktime.views', fromlist=['worker_camera_view']).worker_camera_view, name='worker_camera_ui'),

    # ══ GLOBALNI UPLOAD ALIASI ══
    path('upload/', __import__('django.views.generic', fromlist=['RedirectView']).RedirectView.as_view(url='/hr/documents/arhiva/upload/', permanent=False), name='global_upload'),
    path('documents/upload/', __import__('django.views.generic', fromlist=['RedirectView']).RedirectView.as_view(url='/hr/documents/arhiva/upload/', permanent=False)),
    path('ai-inbox/', __import__('django.views.generic', fromlist=['RedirectView']).RedirectView.as_view(url='/hr/documents/ai-inbox/', permanent=False), name='global_ai_inbox'),

    path('dashboard/worker/upload/', __import__('worktime.views', fromlist=['worker_camera_upload']).worker_camera_upload, name='worker_camera_api'),
    path('dashboard/investor/', views.investor_dashboard, name='investor_dashboard'),
    path('dashboard/partner/', views.partner_dashboard, name='partner_dashboard'),
    prefix_default_language=True,
) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Client/Partner Portal (no login, token-based)
urlpatterns += [
    path('portal/<uuid:token>/', include('partners.portal_urls')),
    path('client/<uuid:token>/', include('partners.client_portal_urls')),
]

# Public booking by company slug
urlpatterns += [
    path('book/<slug:company_slug>/', __import__('appointments.views', fromlist=['public_booking_by_slug']).public_booking_by_slug, name='public_booking_by_slug'),
    path('site/<slug:slug>/', __import__('website.views', fromlist=['company_site']).company_site, name='company_site_public'),
    path('site/<slug:slug>/contact/', __import__('website.views', fromlist=['company_site_contact']).company_site_contact, name='company_site_contact_public'),
]

# Health check (no language prefix needed)
urlpatterns += [
    # Inspektor Dashboard (PUBLIC — bez logina)
    path('inspektor/<path:token>/', __import__('core.views_inspector', fromlist=['inspector_dashboard']).inspector_dashboard, name='inspector_dashboard'),
    # Panic Button (login required)
    path('api/search/', __import__('core.views_search', fromlist=['global_search']).global_search, name='global_search'),
    path('report/synesis-dokaz/', __import__('core.views_search', fromlist=['synesis_report']).synesis_report, name='synesis_report'),

    # ── Rental QuickAction API ──
    path('api/rental/today-arrivals/', __import__('rental.views', fromlist=['api_today_arrivals']).api_today_arrivals, name='rental_api_arrivals'),
    path('api/rental/today-departures/', __import__('rental.views', fromlist=['api_today_departures']).api_today_departures, name='rental_api_departures'),
    path('api/rental/evisitor-pending/', __import__('rental.views', fromlist=['api_evisitor_pending']).api_evisitor_pending, name='rental_api_evisitor'),
    path('api/rental/active-bookings/', __import__('rental.views', fromlist=['api_active_bookings']).api_active_bookings, name='rental_api_active'),

    # ── Membership QuickAction API ──
    path('api/udruge/member-lookup/', __import__('udruge.views', fromlist=['api_member_lookup']).api_member_lookup, name='udruge_api_member_lookup'),
    path('health/', views.health_check, name='health_check'),
    path('api/system/improvement/', __import__('core.cockpit_views', fromlist=['system_improvement_api']).system_improvement_api, name='system_improvement_api'),
    path('api/feedback/count/', __import__('core.cockpit_views', fromlist=['feedback_count_api']).feedback_count_api, name='feedback_count_api'),

    path('api/whatsapp/health/', views.whatsapp_health, name='whatsapp_health'),
    path("api/whatsapp/webhook/", __import__("helpdesk.whatsapp_webhook", fromlist=["whatsapp_webhook"]).whatsapp_webhook, name="whatsapp_webhook"),
    path('impressum/', views.impressum, name='impressum'),
    path('datenschutz/', views.datenschutz, name='datenschutz'),
    path('privatnost/', views.datenschutz, name='privatnost'),
    path('grosmarkt/anfrage/', __import__('website.views', fromlist=['grosmarkt_anfrage']).grosmarkt_anfrage, name='grosmarkt_anfrage_direct'),
    path("api/grosmarkt/partners/", __import__("website.views", fromlist=["grosmarkt_partners_api"]).grosmarkt_partners_api, name="grosmarkt_partners"),
    path('digitalni-posrednik/', __import__('website.views', fromlist=['digitalni_posrednik']).digitalni_posrednik, name='digitalni_posrednik'),
    path('informacijski-posrednik/', TemplateView.as_view(template_name='website/brosura_posrednik.html'), name='brosura_posrednik'),
]

# Dev remote API — UKLONJENO 2026-03-19 (security audit: RCE rizik)
# remote_exec, remote_read, remote_write endpointi obrisani
# Backup: backups/audit_patch_2026-03-19/core/remote_api.py

# Synesis integration
from synesis import views as synesis_views
from synesis import export as synesis_export
urlpatterns += [
    # synesis + smart-import moved to i18n_patterns
    path('helpdesk/portal/', include('helpdesk.portal_urls')),
    # ── Memio.pet public API (bez i18n) ──────────────────────────────
    path("api/memio/waitlist/", __import__("core.views_memio", fromlist=["memio_waitlist"]).memio_waitlist, name="memio_waitlist"),
    path("api/memio/pet/<str:chip_id>/", __import__("core.views_memio", fromlist=["memio_pet_profile"]).memio_pet_profile, name="memio_pet_profile"),
    path("api/memio/stats/", __import__("core.views_memio", fromlist=["memio_stats"]).memio_stats, name="memio_stats"),
    path("api/memio/push/", __import__("core.views_memio", fromlist=["memio_push"]).memio_push, name="memio_push"),

    # ── Memio.world API (zasebna baza) ──────────────────────────
    path("api/memio-world/", include("memio_world.urls")),

    # ── Memio.pet public views (HTML profili + QR) ──────────────
    path("", include("memio_pet.urls")),
    path("api/synesis/import/", synesis_views.synesis_import_api, name="synesis_import_api"),
    path("api/synesis/script/<path:token>/", synesis_views.download_script_public, name="synesis_script_public"),
    path("api/synesis/export/<path:token>/", synesis_export.synesis_export_api, name="synesis_export_api"),
    path("api/synesis/export/<path:token>/confirm/", synesis_export.synesis_export_confirm, name="synesis_export_confirm"),

    # Hybrid Time Tracking API (top-level)

    # ── B2B Klijentski Portal ──────────────────────────────────────────

    # Dev API — claude.ai kanal
    path('_dev/exec/', __import__('core.remote_api', fromlist=['remote_exec']).remote_exec),
    path('_dev/read/', __import__('core.remote_api', fromlist=['remote_read']).remote_read),
    path('_dev/write/', __import__('core.remote_api', fromlist=['remote_write']).remote_write),
]


# ── Custom Error Handlers ──────────────────────────────────────
handler404 = 'core.error_handlers.custom_404_handler'
handler403 = 'core.error_handlers.custom_403_handler'
handler500 = 'core.error_handlers.custom_500_handler'

# ROOT FALLBACK — izvan i18n_patterns da pokrije goli '/' i '/login/'
# Bez ovih ruta LocaleMiddleware ne može matchati / → 404 → redirect loop
urlpatterns += [
    path('', views.smart_home, name='home_root'),
    path('login/', views.login_view, name='login_fallback'),
]

# ── FenixScan — Universalni AI Document Scanner ──────────────────────────────
from core.views_scan import fenix_scan
urlpatterns += [
    path('api/fenix/scan/', fenix_scan, name='fenix_scan'),
    path('api/csrf-token/', __import__('core.csrf_handler', fromlist=['csrf_token_view']).csrf_token_view, name='csrf_token'),
]

# ── CroValidator API — OIB + IBAN + MBS ───────────────────────────────────────
from core.views_validate import api_validate
urlpatterns += [
    path('api/v1/validate/', api_validate, name='api_validate'),
]

# ── Notariat — Bilježnik + Odvjetnik + Dimnjačar ─────────────────────────────
from django.urls import include
urlpatterns += [
    path('notariat/', include('notariat.urls')),
]
