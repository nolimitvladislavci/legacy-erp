"""
0013_populate_module_links.py — Popuni ModuleLink za fina-connect sustav.
"""
from django.db import migrations

FINA_CONNECT_MODULES = [
    # (icon, name, name_short, description, url, category, roles, sort_order, is_admin_only, keywords)
    ("🏠", "Fina-Connect portal",   "Portal",      "Glavni ulaz u ERP sustav",
     "/hr/login/", "portal", [], 1, False, "portal ulaz login fina erp"),

    ("🏢", "Stolovi komitenata",    "Stolovi",     "Raspored komitenata po radnicama — centralna ploča",
     "/hr/companies/stolovi/", "crm", ["bookkeeper","admin"], 10, False, "stol komitent raspored radnica"),
    ("👤", "Odabir komitenata",     "Komitenti",   "Odabir komitenata za radnicu — switch company",
     "/hr/accounts/odaberi-komitente/", "crm", [], 11, False, "komitent odabir switch tvrtka"),

    ("🗄️", "Digitalna arhiva",      "Arhiva",      "Pregled i upload svih poslovnih dokumenata",
     "/hr/documents/arhiva/", "documents", [], 20, False, "arhiva dokument upload pdf scan"),
    ("📤", "Upload dokumenta",      "Upload",      "Brzi upload u digitalnu arhivu",
     "/hr/documents/arhiva/upload/", "documents", [], 21, False, "upload dokument slika pdf"),
    ("🤖", "Smart Import",          "AI uvoz",     "AI uvoz računa — slika/PDF/XML",
     "/hr/smart-import/", "finance", ["bookkeeper","admin"], 22, False, "smart import uvoz ai ocr"),

    ("🏥", "AI Doktor",             "AI Doktor",   "Dijagnoza po firmi — analiza financijskog zdravlja",
     "/hr/ai-cockpit/doktor/", "ai", ["admin","bookkeeper"], 30, False, "ai doktor dijagnoza analiza"),
    ("🎯", "AI Cockpit",            "AI",          "Centralni AI centar",
     "/hr/ai-cockpit/", "ai", ["admin"], 31, True, "ai cockpit inteligencija"),

    ("🐾", "Memio.pet",             "Ljubimci",    "Registar ljubimaca — čipovi, veterinari, putovnice",
     "/hr/pets/", "animals", ["pet_owner","breeder","admin"], 40, False, "memio pet ljubimac čip veterinar"),
    ("🐄", "Stočarstvo",            "Stoka",       "Upravljanje stokom — evidencija, zdravlje",
     "/hr/livestock/", "animals", ["farmer","admin"], 41, False, "stočarstvo stoka govedo farma"),
    ("📋", "Radni nalozi",          "Nalozi",      "Kreiranje i praćenje radnih naloga",
     "/hr/work_orders/", "specialty", ["admin"], 42, False, "radni nalog posao zadatak servis"),
    ("🐦", "Golubarnik",            "Golubar",     "Evidencija golubova i natjecanja",
     "/golubar/", "animals", ["admin"], 43, False, "golubar golub natjecanje trka"),
    ("🛒", "Burza",                 "Tržnica",     "Oglasna burza — ponuda i potražnja",
     "/burza/", "specialty", [], 44, False, "burza tržnica oglas ponuda"),
    ("🧒", "Vrtić",                 "Vrtić",       "Upravljanje dječjim vrtićem",
     "/vrtic/", "social", ["admin"], 45, False, "vrtić dijete predškolac roditelj"),
    ("👴", "Dom umirovljenika",     "Dom",         "Upravljanje domom umirovljenika",
     "/dom/", "social", ["admin"], 46, False, "dom umirovljenik starija osoba skrb"),
    ("📚", "Knjižnica",             "Knjižnica",   "Sustav za knjižnice — knjige, posudba",
     "/lib/staff/", "specialty", ["admin"], 47, False, "knjižnica knjiga posudba katalog"),
    ("🎯", "Lovački savez",         "Lovački",     "Upravljanje lovačkim savezom",
     "/lovacki/", "specialty", ["admin"], 48, False, "lovački savez lovište dozvola"),
    ("🔧", "Utilities",             "Alati",       "Komunalni i infrastrukturni alati",
     "/utilities/", "other", ["admin"], 49, True, "utilities alat infrastruktura"),
    ("🏙️", "Komunalno",            "Komunalno",   "Komunalne usluge",
     "/komunalno/", "specialty", ["admin"], 50, False, "komunalno infrastruktura grad"),
    ("🧠", "Intelligence",          "Intel",       "AI intelligence centar",
     "/intelligence/", "ai", ["admin"], 51, True, "intelligence ai analitika"),
    ("🛒", "Marketplace",           "Online shop", "Online tržnica i e-commerce",
     "/marketplace/", "specialty", [], 52, False, "marketplace tržnica online kupovina"),
    ("🚚", "Dostava",               "Dostava",     "Upravljanje dostavom i logistikom",
     "/delivery/", "specialty", ["admin"], 53, False, "dostava logistika vozač isporuka"),
    ("🍽️", "Gastro meni",           "Gastro",      "Digitalni jelovnik i upravljanje restoranom",
     "/gastro-menu/", "specialty", ["admin"], 54, False, "gastro meni restoran jelo hrana"),
    ("📖", "Knjižnica javna",       "Čitaonica",   "Javna knjižnica — katalog i posudba",
     "/knjiznica/", "specialty", [], 55, False, "knjižnica knjiga katalog čitanje"),
    ("🌿", "Sezonci",               "Sezonci",     "Upravljanje sezonskim radnicima",
     "/sezonci/", "hr", ["admin"], 56, False, "sezonac radnik sezonski rad"),
    ("🐕", "No Limit Azil",         "Azil",        "NO LIMIT — azil za životinje, usvajanja, donacije",
     "/no-limit/", "social", [], 57, False, "azil životinja no limit usvajanje donacija"),
    ("🔐", "Evalidator",            "Eval",        "Digitalna provjera — ChainBlock, certifikati",
     "/evalidator/", "security", ["admin"], 60, False, "eval validator certifikat chainblock"),
    ("🌐", "Klijentski portal",     "Klijent",     "Klijentski portal s token linkom (bez logina)",
     "/client/", "portal", [], 61, False, "klijent portal token link javni"),
    ("📊", "POS onboarding",        "POS wizard",  "Čarobnjak za postavljanje POS blagajne",
     "/hr/pos/onboarding/", "pos", ["admin"], 62, False, "pos blagajna wizard postavljanje"),
]


def populate(apps, schema_editor):
    ModuleLink = apps.get_model("core", "ModuleLink")
    for m in FINA_CONNECT_MODULES:
        icon, name, name_short, description, url, category, roles, sort_order, is_admin_only, keywords = m
        ModuleLink.objects.get_or_create(
            url=url, project="fina-connect",
            defaults=dict(
                icon=icon, name=name, name_short=name_short,
                description=description, category=category,
                roles=roles, sort_order=sort_order,
                is_admin_only=is_admin_only,
                keywords=keywords, is_active=True,
            )
        )


def depopulate(apps, schema_editor):
    apps.get_model("core", "ModuleLink").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0012_module_link")]
    operations = [migrations.RunPython(populate, depopulate)]
