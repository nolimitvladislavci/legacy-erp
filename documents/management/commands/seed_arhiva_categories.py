"""Seed ArhivaCategory with EU tax categories (HR + DE + EU common)."""

from django.core.management.base import BaseCommand

from documents.models import ArhivaCategory

# fmt: off
CATEGORIES = [
    # ─── EU ZAJEDNIČKO ───────────────────────────────────────────
    {"code": "FUEL",     "name_hr": "Gorivo",              "name_de": "Kraftstoff",             "name_en": "Fuel",                "icon": "gas-pump",    "color": "#e67e22", "country": "EU", "skr03_konto": "4530", "skr04_konto": "6530", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "49", "sort_order": 10,  "ai_keywords": ["benzin","diesel","gorivo","ina","petrol","shell","omv","mol","tifon","lukoil","crodux","tankstelle","aral","total","bp","esso","jet"]},
    {"code": "FOOD",     "name_hr": "Hrana i piće",        "name_de": "Lebensmittel",           "name_en": "Food & Beverages",    "icon": "utensils",    "color": "#27ae60", "country": "EU", "skr03_konto": "4654", "skr04_konto": "6644", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "26", "sort_order": 20,  "ai_keywords": ["konzum","spar","lidl","kaufland","müller","billa","hofer","aldi","rewe","edeka","netto","penny","mercator","plodine","tommy","studenac"]},
    {"code": "ENTERTAIN","name_hr": "Reprezentacija",      "name_de": "Bewirtungskosten",       "name_en": "Entertainment",       "icon": "wine-glass",  "color": "#8e44ad", "country": "EU", "skr03_konto": "4650", "skr04_konto": "6640", "pdv_category": "reprezentacija_50", "tax_deductible_pct": 50,  "euer_line": "52", "sort_order": 25,  "ai_keywords": ["restoran","restaurant","kaffee","café","bar","pizzeria","gasthaus","hotel","catering","ručak","večera","mittagessen","abendessen"]},
    {"code": "OFFICE",   "name_hr": "Uredski materijal",   "name_de": "Bürobedarf",             "name_en": "Office Supplies",     "icon": "paperclip",   "color": "#3498db", "country": "EU", "skr03_konto": "4930", "skr04_konto": "6815", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 30,  "ai_keywords": ["papir","tinta","toner","olovka","bilježnica","büromaterial","druckerpapier","stift","ordner","links","müller drogerie"]},
    {"code": "TELECOM",  "name_hr": "Telekomunikacije",    "name_de": "Telekommunikation",      "name_en": "Telecom & Internet",  "icon": "wifi",        "color": "#2980b9", "country": "EU", "skr03_konto": "4920", "skr04_konto": "6805", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 35,  "ai_keywords": ["t-com","a1","telemach","deutsche telekom","vodafone","o2","1&1","congstar","internet","mobitel","telefon","handy"]},
    {"code": "RENT",     "name_hr": "Najam prostora",      "name_de": "Raumkosten / Miete",     "name_en": "Rent / Office",       "icon": "building",    "color": "#34495e", "country": "EU", "skr03_konto": "4210", "skr04_konto": "6310", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "44", "sort_order": 40,  "ai_keywords": ["najam","miete","pacht","zakup","rent","nebenkosten","hausverwaltung"]},
    {"code": "INSURANCE","name_hr": "Osiguranje",          "name_de": "Versicherungen",         "name_en": "Insurance",           "icon": "shield-alt",  "color": "#16a085", "country": "EU", "skr03_konto": "4360", "skr04_konto": "6400", "pdv_category": "neoporezivo",       "tax_deductible_pct": 100, "euer_line": "46", "sort_order": 45,  "ai_keywords": ["osiguranje","versicherung","allianz","grawe","croatia","generali","uniqa","hdi","huk","ergo","axa"]},
    {"code": "VEHICLE",  "name_hr": "Troškovi vozila",     "name_de": "KFZ-Kosten",             "name_en": "Vehicle Costs",       "icon": "car",         "color": "#d35400", "country": "EU", "skr03_konto": "4500", "skr04_konto": "6500", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "49", "sort_order": 50,  "ai_keywords": ["registracija","tehnički","servis","guma","automehaničar","werkstatt","tüv","reifen","inspektion","reparatur","adac","hak"]},
    {"code": "TRAVEL",   "name_hr": "Putni troškovi",      "name_de": "Reisekosten",            "name_en": "Travel",              "icon": "plane",       "color": "#f39c12", "country": "EU", "skr03_konto": "4660", "skr04_konto": "6650", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "51", "sort_order": 55,  "ai_keywords": ["avion","flug","bahn","vlak","bus","taxi","uber","bolt","flixbus","ryanair","lufthansa","croatia airlines","booking","hotel"]},
    {"code": "SERVICES", "name_hr": "Vanjske usluge",      "name_de": "Fremdleistungen",        "name_en": "External Services",   "icon": "hands-helping","color": "#9b59b6", "country": "EU", "skr03_konto": "4900", "skr04_konto": "6300", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "27", "sort_order": 60,  "ai_keywords": ["usluga","dienstleistung","beratung","consulting","savjetovanje","računovodstvo","steuerberater","odvjetnik","rechtsanwalt","notar"]},
    {"code": "TOOLS",    "name_hr": "Alati i oprema",      "name_de": "Werkzeuge & Geräte",     "name_en": "Tools & Equipment",   "icon": "tools",       "color": "#e74c3c", "country": "EU", "skr03_konto": "4985", "skr04_konto": "6845", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 65,  "ai_keywords": ["alat","werkzeug","bohrmaschine","baumarkt","bauhaus","obi","hornbach","bricostore"]},
    {"code": "SOFTWARE", "name_hr": "Software i IT",       "name_de": "Software & IT",          "name_en": "Software & IT",       "icon": "laptop",      "color": "#1abc9c", "country": "EU", "skr03_konto": "4964", "skr04_konto": "6837", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 70,  "ai_keywords": ["software","hosting","domain","cloud","aws","google","microsoft","adobe","apple","github","server","saas","lizenz","licenca"]},
    {"code": "GOODS",    "name_hr": "Nabava robe",         "name_de": "Wareneinkauf",           "name_en": "Goods Purchase",      "icon": "boxes",       "color": "#2c3e50", "country": "EU", "skr03_konto": "3300", "skr04_konto": "5100", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "26", "sort_order": 15,  "ai_keywords": ["roba","ware","einkauf","nabava","materijal","material","rohstoff","halbfertig"]},
    {"code": "POST",     "name_hr": "Pošta i dostava",     "name_de": "Porto & Versand",        "name_en": "Postage & Shipping",  "icon": "envelope",    "color": "#f1c40f", "country": "EU", "skr03_konto": "4910", "skr04_konto": "6800", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 75,  "ai_keywords": ["pošta","hp","post","dhl","dpd","gls","ups","fedex","hermes","paket","brief","versand"]},
    {"code": "BANK",     "name_hr": "Bankarski troškovi",   "name_de": "Bankgebühren",           "name_en": "Bank Fees",           "icon": "university",  "color": "#7f8c8d", "country": "EU", "skr03_konto": "4970", "skr04_konto": "6855", "pdv_category": "neoporezivo",       "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 80,  "ai_keywords": ["banka","bank","sparkasse","volksbank","commerzbank","pbz","zaba","erste","raiffeisen","otp","gebühr","provizija"]},
    {"code": "DEPREC",   "name_hr": "Amortizacija",        "name_de": "Abschreibungen (AfA)",   "name_en": "Depreciation",        "icon": "chart-line",  "color": "#95a5a6", "country": "EU", "skr03_konto": "4830", "skr04_konto": "6220", "pdv_category": "neoporezivo",       "tax_deductible_pct": 100, "euer_line": "30", "sort_order": 85,  "ai_keywords": ["amortizacija","abschreibung","afa","anlage"]},
    {"code": "STAFF",    "name_hr": "Troškovi osoblja",    "name_de": "Personalkosten",         "name_en": "Staff Costs",         "icon": "users",       "color": "#c0392b", "country": "EU", "skr03_konto": "4100", "skr04_konto": "6000", "pdv_category": "neoporezivo",       "tax_deductible_pct": 100, "euer_line": "22", "sort_order": 5,   "ai_keywords": ["plaća","lohn","gehalt","brutto","netto","sozialversicherung","doprinosi","minijob"]},
    {"code": "ADVERTISE","name_hr": "Reklama i marketing", "name_de": "Werbekosten",            "name_en": "Advertising",         "icon": "bullhorn",    "color": "#e91e63", "country": "EU", "skr03_konto": "4600", "skr04_konto": "6600", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "53", "sort_order": 58,  "ai_keywords": ["reklama","werbung","marketing","facebook","google ads","instagram","plakat","flyer","visitenkarte"]},
    {"code": "OTHER",    "name_hr": "Ostali troškovi",     "name_de": "Sonstige Kosten",        "name_en": "Other Expenses",      "icon": "ellipsis-h",  "color": "#bdc3c7", "country": "EU", "skr03_konto": "4900", "skr04_konto": "6300", "pdv_category": "pretporez",         "tax_deductible_pct": 100, "euer_line": "56", "sort_order": 999, "ai_keywords": [], "is_default": True},

    # ─── DE SPECIFIČNO ───────────────────────────────────────────
    {"code": "FAHRTKOSTEN", "name_hr": "Putni troškovi (DE)", "name_de": "Fahrtkosten pauschal", "name_en": "Mileage allowance", "icon": "route", "color": "#e67e22", "country": "DE", "skr03_konto": "4673", "skr04_konto": "6673", "pdv_category": "neoporezivo", "tax_deductible_pct": 100, "euer_line": "51", "sort_order": 56, "ai_keywords": ["kilometergeld","fahrtenbuch","pendlerpauschale","entfernungspauschale"]},
    {"code": "BEWIRTUNG_70", "name_hr": "Ugošćivanje 70% (DE)", "name_de": "Bewirtung (70% absetzbar)", "name_en": "Business meals 70%", "icon": "concierge-bell", "color": "#8e44ad", "country": "DE", "skr03_konto": "4650", "skr04_konto": "6640", "pdv_category": "bewirtung_70", "tax_deductible_pct": 70, "euer_line": "52", "sort_order": 26, "ai_keywords": ["bewirtungsbeleg","geschäftsessen"]},
    {"code": "HOMEOFFICE", "name_hr": "Kućni ured (DE)", "name_de": "Homeoffice-Pauschale", "name_en": "Home office", "icon": "home", "color": "#34495e", "country": "DE", "skr03_konto": "4288", "skr04_konto": "6348", "pdv_category": "neoporezivo", "tax_deductible_pct": 100, "euer_line": "44", "sort_order": 42, "ai_keywords": ["homeoffice","arbeitszimmer","heimarbeit"]},

    # ─── HR SPECIFIČNO ───────────────────────────────────────────
    {"code": "REPREZ_50", "name_hr": "Reprezentacija 50%", "name_de": "Repräsentation 50%", "name_en": "Entertainment 50%", "icon": "glass-cheers", "color": "#8e44ad", "country": "HR", "skr03_konto": "", "skr04_konto": "", "pdv_category": "reprezentacija_50", "tax_deductible_pct": 50, "euer_line": "", "sort_order": 26, "ai_keywords": ["reprezentacija","poslovni ručak","poslovni poklon"]},
    {"code": "DNEVNICA", "name_hr": "Dnevnice", "name_de": "Tagegeld", "name_en": "Per diem", "icon": "calendar-day", "color": "#f39c12", "country": "HR", "skr03_konto": "", "skr04_konto": "", "pdv_category": "neoporezivo", "tax_deductible_pct": 100, "euer_line": "", "sort_order": 57, "ai_keywords": ["dnevnica","putni nalog","službeno putovanje"]},
]
# fmt: on


class Command(BaseCommand):
    help = "Seed ArhivaCategory with EU/DE/HR tax categories"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for cat_data in CATEGORIES:
            keywords = cat_data.pop("ai_keywords", [])
            is_default = cat_data.pop("is_default", False)
            obj, was_created = ArhivaCategory.objects.update_or_create(
                code=cat_data["code"],
                country=cat_data["country"],
                company=None,
                defaults={**cat_data, "ai_keywords": keywords, "is_default": is_default},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"ArhivaCategory: {created} created, {updated} updated"))
