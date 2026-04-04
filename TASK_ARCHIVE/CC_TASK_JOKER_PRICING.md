# CC_TASK_JOKER_PRICING — Pricing stranica po profilu
# Agent: CC Code
# Prioritet: KRITIČAN — bez ovoga novi korisnici ne znaju što kliknuti
# Datum: 2026-03-25

---

## Problem
Trenutna /pricing/ stranica ima 11 kartica ravno. Udruga ne zna što joj treba.
DVD predsjednik zatvori browser za 8 sekundi.

## Rješenje — Joker Pricing
Korisnik odabere profil → vidi 1-3 relevantne kartice → registrira se.

## URL struktura
```
/pricing/                    → landing s 6 profil gumba
/pricing/?profile=udruga     → KUD, DVD, lovci, ribari — 1 kartica: 9,99 EUR
/pricing/?profile=obrtnik    → Paušalac 0 EUR
/pricing/?profile=gastro     → POS/POS+Arhiva/Professional
/pricing/?profile=rental     → Iznajmljivač 9,99 EUR
/pricing/?profile=firma      → Starter/Pro/Enterprise
/pricing/?profile=racunovodja → Arhiva+AI/Enterprise/Distributor
```

## Fix u `website/views.py` — BUG-06

Postoji `pricing_page()` koji ignorira `?profile=` — to je BUG-06.

```python
def pricing_page(request):
    profile = request.GET.get('profile', '').strip().lower()
    
    PROFILE_PLANS = {
        'udruga': ['udruga'],           # samo Udruga plan 9,99 EUR
        'obrtnik': ['pausalarac'],       # Paušalac 0 EUR
        'gastro': ['pos', 'pos_arhiva', 'professional'],
        'rental': ['rental'],
        'firma': ['starter', 'pro', 'enterprise'],
        'racunovodja': ['arhiva_ai', 'enterprise', 'distributor'],
    }
    
    from companies.models import PricingPlan
    if profile and profile in PROFILE_PLANS:
        plan_slugs = PROFILE_PLANS[profile]
        plans = PricingPlan.objects.filter(slug__in=plan_slugs, is_active=True)
    else:
        plans = PricingPlan.objects.filter(is_active=True)
    
    return render(request, 'website/pricing.html', {
        'plans': plans,
        'profile': profile,
        'show_profile_selector': not profile,
    })
```

## Template `website/templates/website/pricing.html`

### Bez profila — prikaži selektor:
```html
<div class="profile-selector">
  <h2>Što opisuje vaš posao?</h2>
  <div class="profile-grid">
    <a href="?profile=udruga" class="profile-card">
      ❤️ Udruga / DVD / KUD
      <small>Članarine, putni nalozi, volonteri</small>
    </a>
    <a href="?profile=obrtnik" class="profile-card">
      🔨 Obrtnik / OPG
      <small>Besplatno za paušalce</small>
    </a>
    <a href="?profile=gastro" class="profile-card">
      🍽 Restoran / Pekara / Caffe
      <small>POS blagajna od 0 EUR</small>
    </a>
    <a href="?profile=rental" class="profile-card">
      🛏 Iznajmljivač / Apartman
      <small>eVisitor, fiskalizacija</small>
    </a>
    <a href="?profile=firma" class="profile-card">
      🏢 d.o.o. / j.d.o.o.
      <small>ERP, invoicing, arhiva</small>
    </a>
    <a href="?profile=racunovodja" class="profile-card">
      👔 Računovođa / Knjigovođa
      <small>Multi-klijent, bulk import</small>
    </a>
  </div>
</div>
```

### S profilom — prikaži filtrirane kartice + "Natrag":
- Link "← Nisam ovo" koji vodi na /pricing/ bez profila
- Max 3 kartice, prominentni CTA "Registriraj se besplatno"
- Za `udruga` profil: istaknuti da je POS BESPLATAN, članarine nefiskalizirane

## 4 kutna gumba (uvijek vidljiva, fiksna pozicija)
```html
<div class="pricing-corners">
  <a href="/pricing/compare/" class="corner-btn">↗ Usporedi sve</a>
  <a href="/register/" class="corner-btn primary">↖ Registracija</a>
  <a href="/demo/" class="corner-btn">↘ Demo</a>
  <a href="https://wa.me/385..." class="corner-btn">↙ WhatsApp</a>
</div>
```

## Definition of Done
- [ ] /pricing/ prikazuje 6 profil kartica
- [ ] /pricing/?profile=udruga prikazuje samo Udruga plan
- [ ] /pricing/?profile=obrtnik prikazuje Paušalac
- [ ] BUG-06 zatvoren
- [ ] Mobile responsive (test na 375px)
- [ ] Commit: `feat: joker pricing — profil selektor, BUG-06 fix`
