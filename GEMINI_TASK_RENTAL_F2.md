# GEMINI_TASK_RENTAL_F2 — AI Asistencija + Obračuni + Upozorenja
## Agent: Gemini | Prioritet: P1

**Čitaj:** RENTAL_MASTER_PLAN.md, CC_TASK_RENTAL_F1.md  
**Preduvjet:** F1 modeli moraju biti u bazi.

---

## MISIJA

Ti si "pametni računovođa u džepu" za iznajmljivača.
Proaktivno upozoravaš, automatski računaš, AI objašnjavaš.

---

## ZADATAK 1: Boravišna pristojba obračun

```python
# rental/tourist_tax.py

from decimal import Decimal

# JLS turistička pristojba 2025 — po skupinama razvijenosti
# Iznajmljivač plaća paušal tromjesečno
TOURIST_TAX_RATES = {
    'high': {'adult': Decimal('2.65'), 'youth': Decimal('1.33'), 'child': Decimal('0')},
    'medium': {'adult': Decimal('1.86'), 'youth': Decimal('0.93'), 'child': Decimal('0')},
    'low': {'adult': Decimal('1.33'), 'youth': Decimal('0.66'), 'child': Decimal('0')},
    'undeveloped': {'adult': Decimal('0.53'), 'youth': Decimal('0.27'), 'child': Decimal('0')},
}

PAUSAL_TAX_RANGES_2025 = {
    # po krevetu godišnje (EUR) — ovisno o JLS skupini
    'group1': (70, 200),   # visokorazvijeni (Dubrovnik, Split...)
    'group2': (50, 150),   # razvijeni
    'group3': (30, 100),   # srednje razvijeni
    'group4': (15, 50),    # nerazvijeni
}


def calculate_quarterly_tax(company, property, quarter: int, year: int) -> dict:
    """
    Izračun tromjesečne boravišne pristojbe za paušalnog iznajmljivača.
    
    Paušalisti plaćaju fiksni iznos PO KREVETU, ne po noćenju.
    Odluku donosi JLS — svaki grad/općina drugačiji iznos.
    
    Returns: {
        'beds': int,
        'pausal_per_bed': Decimal,
        'quarterly_total': Decimal,
        'payment_deadline': date,
        'payment_account': str,  # IBAN TZ
        'payment_reference': str,
    }
    """
    from decimal import Decimal
    from datetime import date
    
    settings = company.settings or {}
    pausal_per_bed = Decimal(str(settings.get('tourist_tax_pausal_per_bed', '40')))
    beds = property.capacity  # broj kreveta/osoba
    
    quarterly = (pausal_per_bed * beds / 4).quantize(Decimal('0.01'))
    
    # Rokovi: 31.7., 31.8., 30.9. (sva tri kvartala za turističku sezonu)
    deadlines = {
        1: date(year, 3, 31),
        2: date(year, 7, 31),
        3: date(year, 8, 31),
        4: date(year, 9, 30),
    }
    
    return {
        'beds': beds,
        'pausal_per_bed': pausal_per_bed,
        'quarterly_total': quarterly,
        'payment_deadline': deadlines.get(quarter),
        'year': year,
        'quarter': quarter,
    }
```

---

## ZADATAK 2: AI Upozorenja (proaktivna)

```python
# rental/ai_assistant.py

import anthropic
from django.utils import timezone

def generate_landlord_daily_brief(company) -> str:
    """
    Haiku generira dnevni sažetak za iznajmljivača.
    Poziva se svako jutro u 08:00 via Celery beat.
    
    PRAVILO: Nikad ne savjetujemo. Samo informiramo.
    """
    from rental.models import Booking, Property
    from decimal import Decimal
    
    today = timezone.now().date()
    
    # Prikupi podatke
    arrivals_today = Booking.objects.filter(
        company=company, check_in=today, status__in=['confirmed', 'pending']
    ).count()
    
    departures_today = Booking.objects.filter(
        company=company, check_out=today, status='checked_in'
    ).count()
    
    active_stays = Booking.objects.filter(
        company=company, status='checked_in'
    ).count()
    
    # Prihodi ovog tjedna
    from datetime import timedelta
    week_end = today + timedelta(days=7)
    week_bookings = Booking.objects.filter(
        company=company,
        check_in__gte=today,
        check_in__lte=week_end,
        status__in=['confirmed', 'pending']
    )
    week_revenue = sum(b.total_price for b in week_bookings)
    
    # YTD primitci
    ytd_revenue = Booking.objects.filter(
        company=company,
        check_out__year=today.year,
        status__in=['checked_out', 'checked_in'],
    ).aggregate(s=__import__('django.db.models',fromlist=['Sum']).Sum('total_price'))['s'] or Decimal('0')
    
    pausal_limit = Decimal('40000')
    limit_percent = (ytd_revenue / pausal_limit * 100).quantize(Decimal('1'))
    
    client = anthropic.Anthropic()
    
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=300,
        messages=[{'role': 'user', 'content': f'''
Napiši kratki jutarnji sažetak za iznajmljivača (HR, max 4 rečenice, konkretno).

Podaci za danas ({today}):
- Dolasci danas: {arrivals_today}
- Odlasci danas: {departures_today}  
- Aktivni gosti: {active_stays}
- Prihodi sljedećih 7 dana: {week_revenue:.2f}€
- YTD prihodi: {ytd_revenue:.2f}€ ({limit_percent}% od 40.000€ paušalnog praga)

PRAVILA:
- Samo informiraj, NE savjetuj
- Ako YTD > 35.000€ → ISTAKNUTO upozorenje o pragu
- Ako dolasci > 0 → podsjeti na eVisitor prijavu u 24h
- Kratko i jasno
'''}]
    )
    
    return msg.content[0].text


def check_annual_limit_warning(company) -> dict:
    """
    Provjeri blizinu 40.000€ paušalnog praga.
    Ako je blizu → WhatsApp upozorenje Mariji i iznajmljivaču.
    """
    from rental.models import Booking
    from decimal import Decimal
    import django.utils.timezone as tz
    
    year = tz.now().year
    ytd = Booking.objects.filter(
        company=company,
        check_out__year=year,
        status__in=['checked_out', 'checked_in'],
    ).aggregate(s=__import__('django.db.models',fromlist=['Sum']).Sum('total_price'))['s'] or Decimal('0')
    
    pausal_limit = Decimal('40000')
    remaining = pausal_limit - ytd
    pct = int(ytd / pausal_limit * 100)
    
    result = {
        'ytd': ytd,
        'limit': pausal_limit,
        'remaining': remaining,
        'percent': pct,
        'warning_level': None,
    }
    
    if pct >= 95:
        result['warning_level'] = 'KRITIČNO'
        result['message'] = f'🔴 UPOZORENJE: Dosegnuto {pct}% godišnjeg praga ({ytd:.0f}€ od 40.000€). Svega {remaining:.0f}€ preostalo do obveze PDV-a i poslovnih knjiga!'
    elif pct >= 80:
        result['warning_level'] = 'VISOKO'
        result['message'] = f'🟠 Pažnja: {pct}% godišnjeg praga ({ytd:.0f}€). Ostalo {remaining:.0f}€. Savjetujte se s računovođom.'
    elif pct >= 60:
        result['warning_level'] = 'UMJERENO'
        result['message'] = f'🟡 Informativan: {pct}% godišnjeg praga ostvareno ({ytd:.0f}€).'
    
    return result
```

---

## ZADATAK 3: TZ-2 obrazac generator

```python
# rental/tz2_generator.py

def generate_tz2_pdf(company, year: int) -> bytes:
    """
    Generira TZ-2 obrazac za godišnju prijavu paušalne boravišne pristojbe.
    Rok predaje: 15. siječnja.
    
    Ovo je PDF koji iznajmljivač predaje Poreznoj upravi.
    """
    from weasyprint import HTML
    from django.template.loader import render_to_string
    from rental.models import Booking, Property
    from django.db.models import Sum
    import decimal
    
    properties = Property.objects.filter(company=company, is_active=True)
    company_settings = company.settings or {}
    
    # Kalkulacija po objektu
    property_data = []
    for prop in properties:
        bookings = Booking.objects.filter(
            rental_property=prop,
            check_out__year=year,
            status__in=['checked_out'],
        )
        total_revenue = bookings.aggregate(s=Sum('total_price'))['s'] or decimal.Decimal('0')
        beds = prop.capacity
        pausal_per_bed = decimal.Decimal(str(company_settings.get('tourist_tax_pausal_per_bed', '40')))
        annual_tax = pausal_per_bed * beds
        
        property_data.append({
            'name': prop.name,
            'location': prop.location,
            'beds': beds,
            'total_revenue': total_revenue,
            'pausal_per_bed': pausal_per_bed,
            'annual_tax': annual_tax,
        })
    
    total_tax = sum(p['annual_tax'] for p in property_data)
    
    html = render_to_string('rental/tz2_form.html', {
        'company': company,
        'year': year,
        'properties': property_data,
        'total_tax': total_tax,
        'deadline': f'15. siječnja {year + 1}.',
    })
    
    return HTML(string=html).write_pdf()
```

---

## ZADATAK 4: Celery taskovi

```python
# rental/tasks.py

from celery import shared_task

@shared_task(name='rental.daily_landlord_brief')
def daily_landlord_brief():
    """Svako jutro 08:00 — šalje sažetak svim iznajmljivačima."""
    from rental.ai_assistant import generate_landlord_daily_brief
    from companies.models import Company
    
    # Firme koje imaju rental module aktivan
    companies = Company.objects.filter(
        rental_properties__isnull=False
    ).distinct()
    
    for company in companies:
        brief = generate_landlord_daily_brief(company)
        # Pošalji WhatsApp vlasniku
        # TODO: connect with notifications.whatsapp


@shared_task(name='rental.check_evisitor_pending')
def check_evisitor_pending():
    """Svakih 6 sati — provjeri bookinge bez eVisitor prijave."""
    from rental.models import Booking, Guest
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(hours=20)  # blizu 24h roka
    
    pending = Booking.objects.filter(
        status='checked_in',
        actual_check_in__lte=cutoff,
    ).filter(
        guests__evisitor_synced=False
    ).distinct()
    
    for booking in pending:
        # WhatsApp upozorenje
        pass


@shared_task(name='rental.annual_limit_check')
def annual_limit_check():
    """Tjedno — provjeri blizinu 40k praga."""
    from rental.ai_assistant import check_annual_limit_warning
    from companies.models import Company
    
    companies = Company.objects.filter(rental_properties__isnull=False).distinct()
    
    for company in companies:
        result = check_annual_limit_warning(company)
        if result.get('warning_level') in ('KRITIČNO', 'VISOKO'):
            # WhatsApp Mariji i iznajmljivaču
            pass
```

## DONE kriterij

```python
from rental.ai_assistant import check_annual_limit_warning
from companies.models import Company
c = Company.objects.first()
result = check_annual_limit_warning(c)
assert 'ytd' in result
assert 'percent' in result
print('✅ Gemini F2 DONE')
```
