"""
Kreira kompletne test podatke u bazi:
- 3 tvrtke (STARTER, BUSINESS, ENTERPRISE)
- 6 korisnika različitih rola
- 5 projektnih upita u različitim statusima
- 3 subscription zapisa
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from django.contrib.auth.models import User
from companies.models import Company
from accounts.models import UserProfile
from burza.models import ProjectLead, LeadActivity

GREEN = '\033[0;32m'; GOLD = '\033[0;33m'; NC = '\033[0m'

def log(msg):  print(f"{GREEN}✓{NC} {msg}")
def warn(msg): print(f"{GOLD}⚠{NC}  {msg}")

print("\n── Kreiranje test podataka ──────────────────────────")

# ── TVRTKE ───────────────────────────────────────────────────
companies_data = [
    {"name": "Visković BAU d.o.o.", "business_type": "doo", "country": "DE",
     "oib": "12345678901", "address": "Schillerstraße 10", "city": "Frankfurt",
     "postal_code": "60313", "email": "info@viskovic-bau.de", "phone": "+4917123456789"},
    {"name": "Konjik Gradnja d.o.o.", "business_type": "doo", "country": "HR",
     "oib": "98765432101", "address": "Trg bana Jelačića 1", "city": "Zagreb",
     "postal_code": "10000", "email": "info@konjik.hr", "phone": "+38512345678"},
    {"name": "Optika Oko d.o.o.", "business_type": "doo", "country": "HR",
     "oib": "11223344556", "address": "Ilica 50", "city": "Zagreb",
     "postal_code": "10000", "email": "info@optika-oko.hr", "phone": "+38512987654"},
]

companies = []
for cd in companies_data:
    c, created = Company.objects.get_or_create(name=cd["name"], defaults=cd)
    companies.append(c)
    action = "kreirana" if created else "već postoji"
    log(f"Tvrtka: {c.name} ({action})")

# ── KORISNICI ────────────────────────────────────────────────
users_data = [
    {"username": "superadmin", "password": "Super123!", "role": "superadmin",
     "company": None, "first_name": "Super", "last_name": "Admin", "email": "super@fina.hr"},
    {"username": "viskovic_admin", "password": "Viskovic123!", "role": "company_admin",
     "company": companies[0], "first_name": "Nikša", "last_name": "Visković", "email": "niksa@viskovic-bau.de"},
    {"username": "viskovic_radnik", "password": "Radnik123!", "role": "worker",
     "company": companies[0], "first_name": "Marko", "last_name": "Marić", "email": "marko@viskovic-bau.de"},
    {"username": "konjik_admin", "password": "Konjik123!", "role": "company_admin",
     "company": companies[1], "first_name": "Ante", "last_name": "Konjik", "email": "ante@konjik.hr"},
    {"username": "optika_admin", "password": "Optika123!", "role": "company_admin",
     "company": companies[2], "first_name": "Marina", "last_name": "Vidović", "email": "marina@optika-oko.hr"},
    {"username": "partner_test", "password": "Partner123!", "role": "partner",
     "company": companies[0], "first_name": "Ivan", "last_name": "Horvat", "email": "ivan@partner.hr"},
]

created_users = []
for ud in users_data:
    user, created = User.objects.get_or_create(
        username=ud["username"],
        defaults={
            "email": ud["email"],
            "first_name": ud["first_name"],
            "last_name": ud["last_name"],
        }
    )
    if created:
        user.set_password(ud["password"])
        user.save()
    
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": ud["role"], "company": ud["company"]}
    )
    created_users.append(user)
    action = "kreiran" if created else "već postoji"
    log(f"Korisnik: {user.username} / {ud['password']} ({ud['role']}) – {action}")

# ── SUBSCRIPTION (ako model postoji) ────────────────────────
try:
    from registration.models import CompanySubscription
    from django.utils import timezone
    from datetime import timedelta

    plans = [
        (companies[0], "business",    59.00),
        (companies[1], "starter",     29.00),
        (companies[2], "enterprise",  99.00),
    ]
    for comp, plan, fee in plans:
        sub, created = CompanySubscription.objects.get_or_create(
            company=comp,
            defaults={
                "plan": plan,
                "monthly_fee": fee,
                "valid_from": timezone.now().date(),
                "valid_until": (timezone.now() + timedelta(days=365)).date(),
                "is_active": True,
            }
        )
        action = "kreirana" if created else "već postoji"
        log(f"Subscription: {comp.name} → {plan.upper()} €{fee}/mj ({action})")
except Exception as e:
    warn(f"Subscription model nije dostupan: {e}")

# ── BURZA UPITI ───────────────────────────────────────────────
leads_data = [
    {
        "company": companies[0], "title": "Kompletna kupaonica 12m² – Frankfurt",
        "description": "Rušenje i izgradnja kupaone od nule. Luksuzne pločice, tuš kabina, dvostruki umivaonik. Rok 3 tjedna.",
        "category": "kupaonica", "location": "Frankfurt am Main",
        "contact_name": "Klaus Müller", "contact_phone": "+4915112345678",
        "contact_email": "k.muller@gmail.com",
        "budget_from": 8000, "budget_to": 12000,
        "status": "NOVI_UPIT", "is_public": False,
    },
    {
        "company": companies[0], "title": "Pločičarski radovi – stan 80m²",
        "description": "Postavljanje pločica u dnevnom boravku, hodnik i 2 kupaonice. Klijent ima vlastiti materijal.",
        "category": "plocice", "location": "Düsseldorf",
        "contact_name": "Anna Schmidt", "contact_phone": "+4917698765432",
        "budget_from": 3500, "budget_to": 5000,
        "status": "INTERNA_PROCJENA", "is_public": False,
    },
    {
        "company": companies[0], "title": "Renovacija stana 65m² – hitno",
        "description": "Kompletna renovacija 2-sobnog stana. Parket, gletanje, bojanje, elektrika. Hitan rok – vlasnik se useljava za 6 tjedana.",
        "category": "renovacija", "location": "Köln",
        "contact_name": "Thomas Weber", "contact_phone": "+4916123456789",
        "budget_from": 15000, "budget_to": 22000,
        "status": "NA_BURZI", "is_public": True,
    },
    {
        "company": companies[0], "title": "Vodoinstalacije – nova gradnja",
        "description": "Postavljanje kompletnih vodoinstalacija u novogradnji. 3 kupaonice, 1 kuhinja, 2 WC-a.",
        "category": "vodoinstal", "location": "Hamburg",
        "contact_name": "Sabine Bauer", "contact_phone": "+4917512345678",
        "budget_from": 6000, "budget_to": 9000,
        "status": "NA_BURZI", "is_public": True,
    },
    {
        "company": companies[1], "title": "Fasaderski radovi – poslovni objekt",
        "description": "Renovacija fasade poslovne zgrade 3 kata. Toplinska izolacija + završni premaz.",
        "category": "fasada", "location": "Zagreb",
        "contact_name": "Stjepan Knežević", "contact_phone": "+38512345678",
        "budget_from": 25000, "budget_to": 40000,
        "status": "PREUZETO", "is_public": False,
    },
]

superadmin_user = created_users[0]
viskovic_user = created_users[1]

for ld in leads_data:
    lead, created = ProjectLead.objects.get_or_create(
        title=ld["title"],
        defaults={**ld, "created_by": viskovic_user}
    )
    if created:
        if ld["status"] == "PREUZETO":
            lead.taken_by = companies[1]
            lead.taken_by_user = created_users[3]
            from django.utils import timezone
            lead.taken_at = timezone.now()
            lead.save()
        LeadActivity.objects.create(
            lead=lead, user=superadmin_user,
            action=f"Test podatak kreiran – status: {ld['status']}",
            new_status=ld["status"]
        )
    action = "kreiran" if created else "već postoji"
    log(f"Lead: {lead.title[:50]} [{lead.status}] ({action})")

print(f"""
╔══════════════════════════════════════════════════════╗
║   TEST PODACI KREIRANI                              ║
╠══════════════════════════════════════════════════════╣
║   LOGIN PODACI:                                     ║
║   superadmin      / Super123!   (superadmin)        ║
║   viskovic_admin  / Viskovic123! (company admin)   ║
║   viskovic_radnik / Radnik123!  (worker)            ║
║   konjik_admin    / Konjik123!  (company admin)    ║
║   optika_admin    / Optika123!  (company admin)    ║
║   partner_test    / Partner123! (partner)           ║
╠══════════════════════════════════════════════════════╣
║   URL: https://limit-connect.com/login/           ║
╚══════════════════════════════════════════════════════╝
""")
