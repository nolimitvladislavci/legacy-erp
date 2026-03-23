"""
Ured u džepu — Onboarding Wizard views + PDF suglasnosti
Endpoint: /partners/wizard/
Endpoint: /partners/wizard/suglasnost-pdf/<session_key>/
"""
import json
import hashlib
from datetime import date
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.company_utils import get_user_company


@login_required
def wizard_view(request):
    """
    7-koračni onboarding wizard — vođeni proces osnivanja firme.
    Korak 1: Što radite? (semantički NKD search — Haiku AI)
    Korak 2: Ime firme
    Korak 3: Broj osnivača + direktor
    Korak 4: Temeljni kapital (d.o.o. / j.d.o.o.)
    Korak 5: Sjedište (vlastita adresa ili "Ured u džepu" = Konjik)
    Korak 6: Pregled + pravne napomene
    Korak 7: Dokumenti (START direktni link ili bilježnik)
    """
    company = get_user_company(request)
    return render(request, 'partners/wizard.html', {
        'company': company,
        'company_address': getattr(company, 'address', ''),
        'company_city': getattr(company, 'city', ''),
        'company_zip': getattr(company, 'zip_code', ''),
        'company_name': getattr(company, 'name', ''),
        'company_oib': getattr(company, 'oib', ''),
    })


@login_required
def wizard_nkd_semantic(request):
    """
    Semantički NKD search — kombinira keyword match s AI opisom.
    Query param: q = slobodna rečenica, npr. "prodaja kave i web shop"
    Returns: [{code, name_hr, name_en, reason}]
    Haiku AI opisuje zašto je svaki kod relevantan.
    """
    from django.http import JsonResponse
    from companies.models import NKDCode
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse([], safe=False)

    # 1. Keyword search u bazi (brzo, bez AI troška)
    keyword_results = list(
        NKDCode.objects.filter(is_active=True).filter(
            Q(name_hr__icontains=q) |
            Q(name_en__icontains=q) |
            Q(code__icontains=q)
        ).values('id', 'code', 'name_hr', 'name_en', 'section')[:10]
    )

    # 2. Ako nema dobrog keyword match-a (< 2 rezultata) ili je upit duži od 15 znakova
    # (slobodna rečenica) — pozovi Haiku za semantičko mapiranje
    if len(keyword_results) < 2 and len(q) > 8:
        haiku_results = _haiku_nkd_suggest(q)
        # Merge — Haiku rezultati nadopunjavaju keyword
        existing_codes = {r['code'] for r in keyword_results}
        for r in haiku_results:
            if r['code'] not in existing_codes:
                keyword_results.append(r)
                existing_codes.add(r['code'])

    return JsonResponse(keyword_results[:8], safe=False)


def _haiku_nkd_suggest(user_description: str) -> list:
    """
    Poziva Haiku API s opisom djelatnosti, vraća listu NKD kodova.
    Haiku prima opis, vraća JSON s kodovima koji odgovaraju.
    """
    import os
    import requests as req

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return []

    from companies.models import NKDCode
    # Daj Haiku-u samo kodove i nazive (ne cijelu bazu) — token limit
    all_nkd = list(
        NKDCode.objects.filter(is_active=True)
        .values_list('code', 'name_hr')
        .order_by('code')
    )
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
        # Čišćenje mogućih backtick omotača
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        suggestions = json.loads(text)

        # Obogati s podacima iz baze
        results = []
        for s in suggestions:
            code = s.get('code', '').strip()
            nkd = NKDCode.objects.filter(code=code, is_active=True).first()
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
    except Exception:
        return []


@login_required
def wizard_suglasnost_pdf(request):
    """
    Generira PDF suglasnosti za korištenje adrese računovodstva.
    POST params: klijent_ime, klijent_oib, klijent_direktor
    """
    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    else:
        data = request.GET

    company = get_user_company(request)
    klijent_ime = data.get('klijent_ime', '').strip()
    klijent_oib = data.get('klijent_oib', '').strip()
    klijent_direktor = data.get('klijent_direktor', '').strip()

    if not klijent_ime:
        return JsonResponse({'error': 'Nedostaje ime klijenta'}, status=400)

    html = _render_suglasnost_html(
        racunovodstvo=company,
        klijent_ime=klijent_ime,
        klijent_oib=klijent_oib,
        klijent_direktor=klijent_direktor,
        datum=date.today(),
    )

    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        filename = f'suglasnost-sjediste-{klijent_oib or klijent_ime[:10]}.pdf'
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _render_suglasnost_html(racunovodstvo, klijent_ime, klijent_oib,
                             klijent_direktor, datum) -> str:
    """
    HTML predložak za Suglasnost za korištenje adrese sjedišta.
    Pravna osnova: ZTD čl. 36 — sjedište mora biti u RH,
    ne mora biti vlastito — dovoljna pisana suglasnost vlasnika prostora.
    """
    r_ime = getattr(racunovodstvo, 'name', 'Konjik d.o.o.')
    r_oib = getattr(racunovodstvo, 'oib', '')
    r_adr = getattr(racunovodstvo, 'address', '')
    r_grad = getattr(racunovodstvo, 'city', '')
    r_zip = getattr(racunovodstvo, 'zip_code', '')
    r_direktor = ''

    datum_str = datum.strftime('%d. %m. %Y.')

    return f"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.7; color: #111; }}
  .header {{ text-align: center; margin-bottom: 2em; }}
  .title {{ font-size: 16pt; font-weight: bold; text-transform: uppercase;
             letter-spacing: 1px; margin: 1em 0 0.3em; }}
  .subtitle {{ font-size: 10pt; color: #555; }}
  .body-text {{ margin: 1.5em 0; text-align: justify; }}
  .potpisnici {{ display: flex; justify-content: space-between; margin-top: 4em; }}
  .potpis-box {{ width: 45%; }}
  .potpis-line {{ border-bottom: 1px solid #333; margin-top: 4em; margin-bottom: 0.3em; }}
  .potpis-label {{ font-size: 9pt; color: #555; }}
  .legal-note {{ font-size: 9pt; color: #777; border-top: 1px solid #ddd;
                  padding-top: 1em; margin-top: 3em; }}
  .bold {{ font-weight: bold; }}
</style>
</head>
<body>

<div class="header">
  <div class="title">Suglasnost za korištenje adrese sjedišta</div>
  <div class="subtitle">temeljem čl. 36. Zakona o trgovačkim društvima (NN 111/93 i izmj.)</div>
</div>

<p class="body-text">
  Ja, <span class="bold">{r_ime}</span> (OIB: {r_oib}), sa sjedištem na adresi
  <span class="bold">{r_adr}, {r_zip} {r_grad}</span>,
  kao vlasnik/korisnik navedenog poslovnog prostora,
</p>

<p class="body-text">
  ovom izjavom dajem <span class="bold">suglasnost</span> trgovačkom društvu
  <span class="bold">{klijent_ime}</span>
  {f'(OIB: {klijent_oib}),' if klijent_oib else ''}
  zastupano po direktoru <span class="bold">{klijent_direktor or '___________________________'}</span>,
  da koristi adresu
</p>

<p style="text-align:center; font-size:14pt; font-weight:bold; margin: 1.5em 0;">
  {r_adr}, {r_zip} {r_grad}
</p>

<p class="body-text">
  kao <span class="bold">sjedište društva</span> pri registraciji u sudski registar Republike Hrvatske.
</p>

<p class="body-text">
  Ova suglasnost izdaje se u svrhu upisa u sudski registar sukladno odredbama Zakona o
  trgovačkim društvima te ne implicira zakupni niti bilo koji drugi imovinskopravni odnos
  između stranaka. Suglasnost se može opozvati pisanom obaviješću uz otkazni rok od 30 dana.
</p>

<p class="body-text">
  Primatelj suglasnosti dužan je odmah po primitku pisane obavijesti o opozivu pokrenuti
  postupak promjene sjedišta društva u sudskom registru.
</p>

<div class="potpisnici">
  <div class="potpis-box">
    <div class="potpis-line"></div>
    <div class="potpis-label">
      <strong>Davatelj suglasnosti</strong><br>
      {r_ime}<br>
      {r_adr}, {r_grad}<br>
      Datum: {datum_str}
    </div>
  </div>
  <div class="potpis-box">
    <div class="potpis-line"></div>
    <div class="potpis-label">
      <strong>Primatelj suglasnosti</strong><br>
      {klijent_ime}<br>
      Direktor: {klijent_direktor or '___________________________'}<br>
      Datum: {datum_str}
    </div>
  </div>
</div>

<div class="legal-note">
  Sukladno čl. 36. ZTD-a, sjedište trgovačkoga društva je mjesto u RH u kojemu je uprava
  društva ili odakle se upravlja poslovima. Sud neće odbiti prijavu samo zbog toga što je
  adresa sjedišta adresa pružatelja usluga (računovodstveni servis, virtualni ured) —
  uz predočenje ove suglasnosti. Vidi: Rješenje VTS-a, klasa: I-1504/00.
</div>

</body>
</html>"""


@login_required
def wizard_preview(request):
    """
    AJAX endpoint — vraća preview podataka za korak 6 wizarda.
    Validira i priprema dokumentaciju.
    """
    data = json.loads(request.body)
    errors = []

    firma_ime = data.get('firma_ime', '').strip()
    if not firma_ime:
        errors.append('Ime firme je obavezno.')
    if len(firma_ime) < 3:
        errors.append('Ime firme mora imati najmanje 3 znaka.')

    nkd_ids = data.get('nkd_ids', [])
    if not nkd_ids:
        errors.append('Odaberite barem jednu djelatnost.')

    broj_osnivaca = data.get('broj_osnivaca', 1)
    try:
        broj_osnivaca = int(broj_osnivaca)
    except (ValueError, TypeError):
        broj_osnivaca = 1

    kapital = data.get('kapital', 'jdoo')
    koristi_konjik = data.get('koristi_konjik', False)

    # Provjeri NKD-ove
    from companies.models import NKDCode
    nkd_objects = list(NKDCode.objects.filter(id__in=nkd_ids, is_active=True).values('code', 'name_hr'))

    # Procijeni put registracije
    if broj_osnivaca > 3:
        registration_path = 'biljeznik'  # START ne podržava > 3 osnivača
        registration_note = 'Više od 3 osnivača — potreban javni bilježnik ili e-Notar.'
    else:
        registration_path = 'start'
        registration_note = 'Može se registrirati online putem sustava START (3,98 EUR). Potrebna eOsobna iskaznica.'

    return JsonResponse({
        'valid': len(errors) == 0,
        'errors': errors,
        'summary': {
            'firma_ime': firma_ime,
            'kapital': '1 EUR' if kapital == 'jdoo' else '2.500 EUR',
            'tip': 'j.d.o.o.' if kapital == 'jdoo' else 'd.o.o.',
            'broj_osnivaca': broj_osnivaca,
            'nkd': nkd_objects,
            'sjediste': 'Konjik d.o.o. (suglasnost)' if koristi_konjik else 'Vlastita adresa',
            'registration_path': registration_path,
            'registration_note': registration_note,
        }
    })
