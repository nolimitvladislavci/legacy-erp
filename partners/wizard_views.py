"""
Ured u džepu — Wizard views s perzistencijom
Svaki "Dalje" okida AJAX save → WizardDraft se ažurira u bazi.
Korak 0 = T&C gatekeeper (GDPR).
"""
import json
import secrets
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.company_utils import get_user_company
from partners.models import WizardDraft

# ─── helpers ────────────────────────────────────────────────────────────────

def _get_or_create_draft(request) -> WizardDraft:
    """
    Draft se identifikacira session_key koji živi u cookie-u.
    Ako ne postoji → kreira novi, vezan na accounting_firm tekućeg usera.
    """
    key = request.session.get('wizard_draft_key')
    if key:
        draft = WizardDraft.objects.filter(session_key=key).first()
        if draft:
            return draft
    # Novi draft
    key = secrets.token_urlsafe(32)
    request.session['wizard_draft_key'] = key
    company = get_user_company(request)
    draft = WizardDraft.objects.create(
        session_key=key,
        ip_address=_get_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        accounting_firm=company,
    )
    return draft


def _get_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


def _draft_to_dict(draft: WizardDraft) -> dict:
    return {
        'session_key': draft.session_key,
        'current_step': draft.current_step,
        'tc_accepted': draft.tc_accepted,
        'nkd_codes_json': draft.nkd_codes_json,
        'firma_ime': draft.firma_ime,
        'broj_osnivaca': draft.broj_osnivaca,
        'direktor_ime': draft.direktor_ime,
        'direktor_oib': draft.direktor_oib,
        'direktor_email': draft.direktor_email,
        'kapital_tip': draft.kapital_tip,
        'koristi_konjik': draft.koristi_konjik,
        'sjediste_adresa': draft.sjediste_adresa,
        'sjediste_grad': draft.sjediste_grad,
        'sjediste_zip': draft.sjediste_zip,
        'completed': draft.completed,
        'pending_company_id': draft.pending_company_id,
    }


# ─── views ──────────────────────────────────────────────────────────────────

@login_required
def wizard_view(request):
    company = get_user_company(request)
    draft = _get_or_create_draft(request)

    # Ako je draft iz prethodne sesije — ponudi nastavak
    resume = draft.current_step > 0 and not draft.completed

    return render(request, 'partners/wizard.html', {
        'company': company,
        'company_name': getattr(company, 'name', ''),
        'company_address': getattr(company, 'address', ''),
        'company_city': getattr(company, 'city', ''),
        'company_zip': getattr(company, 'zip_code', ''),
        'company_oib': getattr(company, 'oib', ''),
        'draft': _draft_to_dict(draft),
        'draft_json': json.dumps(_draft_to_dict(draft)),
        'resume': resume,
    })


@login_required
@require_POST
def wizard_save_step(request):
    """
    AJAX endpoint — sprema state pojedinog koraka.
    Body: { step: int, data: {...} }
    Svaki korak sprema samo svoja polja — StateValidator na frontendu
    garantira da su podaci čisti prije slanja.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    step = int(body.get('step', 0))
    data = body.get('data', {})

    draft = _get_or_create_draft(request)

    # Korak 0 — T&C prihvat (GDPR gatekeeper)
    if step == 0:
        if not data.get('tc_accepted'):
            return JsonResponse({'ok': False, 'error': 'T&C nije prihvaćen'}, status=400)
        draft.tc_accepted = True
        draft.tc_accepted_at = timezone.now()

    # Korak 1 — NKD djelatnosti
    elif step == 1:
        nkd = data.get('nkd_codes', [])
        if not nkd:
            return JsonResponse({'ok': False, 'error': 'Odaberite barem jednu djelatnost'}, status=400)
        draft.nkd_codes_json = nkd  # [{id, code, name_hr}]

    # Korak 2 — ime firme + Company(pending) factory
    elif step == 2:
        ime = data.get('firma_ime', '').strip()
        if len(ime) < 3:
            return JsonResponse({'ok': False, 'error': 'Unesite ime firme'}, status=400)
        draft.firma_ime = ime

        # Kreiraj pending Company ako još ne postoji
        if not draft.pending_company_id:
            draft.pending_company = _create_pending_company(
                name=ime,
                accounting_firm=draft.accounting_firm,
                created_by=request.user,
            )

    # Korak 3 — osnivači
    elif step == 3:
        draft.broj_osnivaca = int(data.get('broj_osnivaca', 1))
        draft.direktor_ime = data.get('direktor_ime', '').strip()
        draft.direktor_oib = data.get('direktor_oib', '').strip()
        draft.direktor_email = data.get('direktor_email', '').strip()

    # Korak 4 — oblik društva
    elif step == 4:
        kapital = data.get('kapital_tip', 'jdoo')
        if kapital not in ('jdoo', 'doo'):
            kapital = 'jdoo'
        draft.kapital_tip = kapital

    # Korak 5 — sjedište
    elif step == 5:
        draft.koristi_konjik = bool(data.get('koristi_konjik', True))
        if not draft.koristi_konjik:
            draft.sjediste_adresa = data.get('sjediste_adresa', '').strip()
            draft.sjediste_grad = data.get('sjediste_grad', '').strip()
            draft.sjediste_zip = data.get('sjediste_zip', '').strip()
        # Ažuriraj pending company s NKD-om
        _sync_pending_company(draft)

    # Korak 6 — preview (read-only, nema save)
    # Korak 7 — završetak
    elif step == 7:
        draft.completed = True
        draft.completed_at = timezone.now()
        _finalize_draft(draft, request.user)

    # Update current_step — nikad ne idi unazad
    if step > draft.current_step:
        draft.current_step = step

    draft.save()

    return JsonResponse({
        'ok': True,
        'draft': _draft_to_dict(draft),
    })


@login_required
def wizard_step_preview(request):
    """
    Korak 6 — StateValidator pull svih podataka iz drafta + validacija.
    """
    draft = _get_or_create_draft(request)

    errors = []
    if not draft.tc_accepted:
        errors.append('T&C nije prihvaćen.')
    if not draft.nkd_codes_json:
        errors.append('Odaberite barem jednu djelatnost.')
    if not draft.firma_ime:
        errors.append('Unesite ime firme.')

    return JsonResponse({
        'valid': len(errors) == 0,
        'errors': errors,
        'summary': {
            'firma_ime': draft.firma_ime,
            'tip': 'j.d.o.o.' if draft.kapital_tip == 'jdoo' else 'd.o.o.',
            'kapital': '1 EUR' if draft.kapital_tip == 'jdoo' else '2.500 EUR',
            'broj_osnivaca': draft.broj_osnivaca,
            'sjediste': 'Konjik d.o.o. (suglasnost)' if draft.koristi_konjik else
                        f'{draft.sjediste_adresa}, {draft.sjediste_grad}',
            'nkd': draft.nkd_codes_json,
            'registration_path': draft.registration_path,
            'registration_note': (
                'Može se registrirati online — START (3,98 EUR). Treba eOsobna iskaznica.'
                if draft.registration_path == 'start' else
                'Više od 3 osnivača — potreban javni bilježnik ili e-Notar.'
            ),
            'pending_company_id': draft.pending_company_id,
        }
    })


@login_required
def wizard_nkd_semantic(request):
    """
    Semantički NKD search — keyword + Haiku AI fallback.
    """
    from django.db.models import Q

    from companies.models import NKDCode

    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse([], safe=False)

    keyword_results = list(
        NKDCode.objects.filter(is_active=True).filter(
            Q(name_hr__icontains=q) | Q(name_en__icontains=q) | Q(code__icontains=q)
        ).values('id', 'code', 'name_hr', 'name_en', 'section')[:10]
    )

    # AI fallback: slobodna rečenica s malo keyword hitova
    if len(keyword_results) < 2 and len(q) > 8:
        ai_results = _haiku_nkd_suggest(q)
        seen = {r['code'] for r in keyword_results}
        for r in ai_results:
            if r['code'] not in seen:
                keyword_results.append(r)
                seen.add(r['code'])

    return JsonResponse(keyword_results[:8], safe=False)


@login_required
def wizard_suglasnost_pdf(request):
    """
    Generira PDF suglasnosti za korištenje adrese sjedišta.
    Povlači podatke iz WizardDraft ili direktno iz GET/POST parametara.
    """
    draft = _get_or_create_draft(request)
    company = get_user_company(request)

    # Preferira draft podatke, fallback na query parametre
    klijent_ime = draft.firma_ime or request.GET.get('klijent_ime', '')
    klijent_oib = draft.direktor_oib or request.GET.get('klijent_oib', '')
    klijent_direktor = draft.direktor_ime or request.GET.get('klijent_direktor', '')

    if not klijent_ime:
        return JsonResponse({'error': 'Nedostaje ime klijenta'}, status=400)

    html = _render_suglasnost_html(company, klijent_ime, klijent_oib, klijent_direktor, date.today())

    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        filename = f'suglasnost-sjediste-{klijent_oib or klijent_ime[:10]}.pdf'
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
    except ImportError as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def wizard_reset(request):
    """Briše draft i počinje iznova."""
    key = request.session.pop('wizard_draft_key', None)
    if key:
        WizardDraft.objects.filter(session_key=key).delete()
    return JsonResponse({'ok': True})


# ─── company factory ─────────────────────────────────────────────────────────

def _create_pending_company(name: str, accounting_firm, created_by) -> 'Company':
    """
    Kreira Company objekt sa statusom 'pending_onboarding'.
    OIB se ne zna još — koristimo placeholder koji treba biti ažuriran.
    business_type = 'jdoo' default.
    """
    import uuid

    from companies.models import Company, CompanyPartnership

    placeholder_oib = f'DRAFT{uuid.uuid4().hex[:6].upper()}'
    company = Company.objects.create(
        name=name,
        oib=placeholder_oib,
        business_type='jdoo',
    )

    # Veži na računovođu — CompanyPartnership
    if accounting_firm:
        CompanyPartnership.objects.get_or_create(
            partner_company=accounting_firm,
            managed_company=company,
            defaults={
                'billing_type': 'monthly',
                'access_level': 'admin',
            }
        )

    return company


def _sync_pending_company(draft: WizardDraft):
    """
    Nakon koraka 5 (sjedište) — ažurira pending Company s dostupnim podacima.
    NKD primarni kod se postavlja.
    """
    if not draft.pending_company_id:
        return
    try:
        company = draft.pending_company
        if draft.nkd_codes_json:
            from companies.models import NKDCode
            first_nkd_id = draft.nkd_codes_json[0].get('id') if isinstance(draft.nkd_codes_json[0], dict) else None
            if first_nkd_id:
                nkd = NKDCode.objects.filter(id=first_nkd_id).first()
                if nkd:
                    company.nkd_code = nkd
        company.business_type = draft.kapital_tip
        if draft.koristi_konjik and draft.accounting_firm:
            company.address = getattr(draft.accounting_firm, 'address', '')
            company.city = getattr(draft.accounting_firm, 'city', '')
            company.zip_code = getattr(draft.accounting_firm, 'zip_code', '')
        elif not draft.koristi_konjik:
            company.address = draft.sjediste_adresa
            company.city = draft.sjediste_grad
            company.zip_code = draft.sjediste_zip
        company.save()
    except (IntegrityError, DatabaseError):
        pass  # Nikad ne blokiraj wizard zbog sync greške


def _finalize_draft(draft: WizardDraft, user):
    """
    Korak 7 — wizard završen.
    Kreira OnboardingProgress za pending Company.
    """
    if not draft.pending_company_id:
        return
    try:
        from companies.models import OnboardingProgress
        OnboardingProgress.objects.get_or_create(
            company=draft.pending_company,
            defaults={'profile_completed': False}
        )
    except DatabaseError:
        pass


# ─── Haiku NKD semantic ──────────────────────────────────────────────────────

def _haiku_nkd_suggest(user_description: str) -> list:
    import os

    import requests as req

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return []

    from companies.models import NKDCode
    all_nkd = list(NKDCode.objects.filter(is_active=True).values_list('code', 'name_hr').order_by('code'))
    nkd_list_str = '\n'.join(f'{c}: {n}' for c, n in all_nkd)

    prompt = (
        f'Korisnik opisuje svoju buduću poslovnu djelatnost: "{user_description}"\n\n'
        f'Dostupni NKD kodovi:\n{nkd_list_str}\n\n'
        f'Vrati JSON listu (max 5) NKD kodova koji NAJBOIJE odgovaraju opisu.\n'
        f'Format: [{{"code": "47.91", "reason": "kratko objašnjenje na hr"}}]\n'
        f'Vrati SAMO JSON, bez ikakvog teksta oko njega.'
    )

    try:
        resp = req.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 300,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=8,
        )
        resp.raise_for_status()
        text = resp.json()['content'][0]['text'].strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        suggestions = json.loads(text)

        results = []
        for s in suggestions:
            from companies.models import NKDCode
            nkd = NKDCode.objects.filter(code=s.get('code', ''), is_active=True).first()
            if nkd:
                results.append({
                    'id': nkd.id,
                    'code': nkd.code,
                    'name_hr': nkd.name_hr,
                    'name_en': nkd.name_en,
                    'section': nkd.section,
                    'ai_reason': s.get('reason', ''),
                })
        return results
    except (json.JSONDecodeError, ValueError):
        return []


# ─── PDF suglasnost ──────────────────────────────────────────────────────────

def _render_suglasnost_html(company, klijent_ime, klijent_oib, klijent_direktor, datum) -> str:
    r_ime = getattr(company, 'name', 'Konjik d.o.o.')
    r_oib = getattr(company, 'oib', '')
    r_adr = getattr(company, 'address', '')
    r_grad = getattr(company, 'city', '')
    r_zip = getattr(company, 'zip_code', '')
    datum_str = datum.strftime('%d. %m. %Y.')

    return f"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.7; color: #111; }}
  .header {{ text-align: center; margin-bottom: 2em; }}
  .title {{ font-size: 16pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin: 1em 0 0.3em; }}
  .subtitle {{ font-size: 10pt; color: #555; }}
  .body-text {{ margin: 1.5em 0; text-align: justify; }}
  .potpisnici {{ display: flex; justify-content: space-between; margin-top: 4em; }}
  .potpis-box {{ width: 45%; }}
  .potpis-line {{ border-bottom: 1px solid #333; margin-top: 4em; margin-bottom: 0.3em; }}
  .potpis-label {{ font-size: 9pt; color: #555; }}
  .legal-note {{ font-size: 9pt; color: #777; border-top: 1px solid #ddd; padding-top: 1em; margin-top: 3em; }}
  .bold {{ font-weight: bold; }}
</style>
</head>
<body>
<div class="header">
  <div class="title">Suglasnost za korištenje adrese sjedišta</div>
  <div class="subtitle">temeljem čl. 36. Zakona o trgovačkim društvima (NN 111/93 i izmjenama)</div>
</div>
<p class="body-text">
  Ja, <span class="bold">{r_ime}</span> (OIB: {r_oib}), sa sjedištem na adresi
  <span class="bold">{r_adr}, {r_zip} {r_grad}</span>, kao vlasnik/korisnik navedenog poslovnog prostora,
</p>
<p class="body-text">
  ovom izjavom dajem <span class="bold">suglasnost</span> trgovačkom društvu
  <span class="bold">{klijent_ime}</span>{f' (OIB direktora: {klijent_oib}),' if klijent_oib else ','}
  zastupano po direktoru <span class="bold">{klijent_direktor or '___________________________'}</span>,
  da koristi adresu
</p>
<p style="text-align:center;font-size:14pt;font-weight:bold;margin:1.5em 0">
  {r_adr}, {r_zip} {r_grad}
</p>
<p class="body-text">
  kao <span class="bold">sjedište društva</span> pri registraciji u sudski registar Republike Hrvatske.
</p>
<p class="body-text">
  Ova suglasnost izdaje se u svrhu upisa u sudski registar sukladno odredbama Zakona o
  trgovačkim društvima te ne implicira zakupni niti bilo koji drugi imovinskopravni odnos
  između stranaka. Suglasnost se može opozvati pisanom obaviješću uz otkazni rok od 30 dana.
  Primatelj suglasnosti dužan je odmah po primitku obavijesti pokrenuti postupak promjene sjedišta.
</p>
<div class="potpisnici">
  <div class="potpis-box">
    <div class="potpis-line"></div>
    <div class="potpis-label">
      <strong>Davatelj suglasnosti</strong><br>{r_ime}<br>{r_adr}, {r_grad}<br>Datum: {datum_str}
    </div>
  </div>
  <div class="potpis-box">
    <div class="potpis-line"></div>
    <div class="potpis-label">
      <strong>Primatelj suglasnosti</strong><br>{klijent_ime}<br>
      Direktor: {klijent_direktor or '___________________________'}<br>Datum: {datum_str}
    </div>
  </div>
</div>
<div class="legal-note">
  Sukladno čl. 36. ZTD-a, sjedište ne mora biti vlastiti prostor — dovoljna je pisana suglasnost
  vlasnika prostora. Uz predočenje ove suglasnosti sud neće odbiti prijavu (VTS, klasa: I-1504/00).
</div>
</body></html>"""
