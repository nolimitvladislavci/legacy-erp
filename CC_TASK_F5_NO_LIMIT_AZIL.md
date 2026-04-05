# CC TASK F5 — NO LIMIT Azil: Mobile POS + Landing
# Prioritet: 🔥 ODMAH | Rok: 09.04.2026.
# Assignee: Claude Code
# Koncepcija: Ivan Brtan / NO LIMIT udruga

## VIZIJA
Azil za životinje dobiva LIMIT Connect BESPLATNO.
POS na mobitelu. Fiskalizacija. Sav posao — osim čitanja čipa (Bluetooth uređaj).
Medijska priča: "digitalni sponzor azila" = ambasadori + press + besplatni onboarding.

## ZADACI

### 1. Tenant tip: AZIL
PROVJERI modele tenant-a:
```bash
grep -n "tenant_type\|TenantProfile\|industry" /var/www/fina-connect/accounts/models.py | head -20
grep -rn "INDUSTRIES\|tenant_type" /var/www/fina-connect/core/ | head -10
```

Dodaj (ako ne postoji): `tenant_type = 'azil'` u choices za tenant.
Azil ima: besplatan plan, unlimited, zauvijek.

### 2. Azil konfiguracija (POS profil)
Azil POS specifičnosti:
- Artikli: "Usvajanje psa", "Usvajanje mačke", "Donacija", "Medicinska naknada"
- Fiskalizacija: DA (udruga mora fiskal. ako promet > 0)
- Bez skladišta (SIMPLE mode)
- Bez kupca OIB (fizička osoba, neobvezno)

Kreiraj management komandu:
```bash
python manage.py setup_azil_tenant --name="Azil Osijek" --oib="..."
```
Koja automatski:
- Kreira tenant (besplatni plan)
- Kreira 4 default artikla
- Kreira POS terminal
- Ispiše login podatke

### 3. Mobile POS page — azil skin
Provjeri postojeći POS template:
```bash
ls /var/www/fina-connect/templates/pos/
```

Azil skin: lagana modifikacija postojećeg POS-a:
- Favicon/logo: šapa umjesto F logo
- Boja shema: topla (amber/orange) umjesto plave
- Default artikli odmah vidljivi (ne traži se pretraživanje)
- Big buttons — dizajnirani za volontere, ne blagajnike

Dodaj CSS klasu `.theme-azil` na body ako `tenant.tenant_type == 'azil'`.

### 4. Landing page: limit-connect.com/azil/
Template: `templates/azil/landing.html`

Sadržaj:
- Hero: "Vaš azil zaslužuje digitalni alat. Besplatno. Zauvijek."
- Što dobivaju: POS na mobitelu / Fiskalizacija / Donacije / Statistike
- Što NE trebaju: hardware, godišnji ugovor, IT znanje
- Jedino što trebaju: Bluetooth čitač čipova (~30€, Amazon)
- CTA: "Prijavite vaš azil" → forma (ime azila, OIB, ime kontakt osobe, email)
- Footer: "Projekt udruge NO LIMIT | Predsjednik: Ivan Brtan | ivan@limit-connect.com"

### 5. Azil waitlist model (ako ne postoji)
```python
class AzilWaitlist(models.Model):
    azil_name = models.CharField(max_length=200)
    oib = models.CharField(max_length=11, blank=True)
    contact_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100)
    num_animals = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_activated = models.BooleanField(default=False)
```
Migrate. Admin panel za Ivan da vidi prijave.

## COMMITI
Format: `feat(azil): [opis]`
Minimalno 4: model/config, mobile-skin, landing, waitlist
