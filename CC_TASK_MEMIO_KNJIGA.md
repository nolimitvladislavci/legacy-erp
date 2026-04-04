# CC TASK: MEMIO PROMOTIVNA KNJIGA + NO-LIMIT INTEGRACIJA
Datum: 04.04.2026. | Rok: 07.04.2026.
Prioritet: VISOK — marketinški alat za azile i javni poziv

PRAVILO: READ svaki fajl koji modificiraš PRIJE pisanja.
PRAVILO: templates/base.html NE DIRAŠ.
PRAVILO: Nakon svakog koraka: venv/bin/python manage.py check 2>&1 | tail -3

---

## KORAK 1 — Provjeri no_limit app strukturu

EXEC: ls /var/www/fina-connect/no_limit/
EXEC: ls /var/www/fina-connect/no_limit/templates/no_limit/ 2>/dev/null || echo "nema templates"
EXEC: cat /var/www/fina-connect/no_limit/models.py
EXEC: cat /var/www/fina-connect/no_limit/urls.py

---

## KORAK 2 — Dodaj AzilPrijava model

READ: /var/www/fina-connect/no_limit/models.py

Na kraj fajla dodaj model:

class AzilPrijava(models.Model):
    naziv = models.CharField(max_length=200, verbose_name="Naziv azila/udruge")
    email = models.EmailField(verbose_name="Email kontakt")
    grad = models.CharField(max_length=100)
    poruka = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    contacted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Prijava azila"
        verbose_name_plural = "Prijave azila"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.naziv} ({self.grad})"

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py makemigrations no_limit
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py migrate no_limit

---

## KORAK 3 — Registriraj u admin

READ: /var/www/fina-connect/no_limit/admin.py

Dodaj:
from no_limit.models import AzilPrijava

@admin.register(AzilPrijava)
class AzilPrijavadmin(admin.ModelAdmin):
    list_display = ("naziv", "grad", "email", "contacted", "created_at")
    list_filter = ("contacted", "grad")
    search_fields = ("naziv", "email")
    actions = ["oznaci_contacted"]

    def oznaci_contacted(self, request, queryset):
        queryset.update(contacted=True)
    oznaci_contacted.short_description = "Oznaci kao kontaktirano"

---

## KORAK 4 — PDF template (WeasyPrint)

EXEC: mkdir -p /var/www/fina-connect/no_limit/templates/no_limit/pdf/

WRITE: /var/www/fina-connect/no_limit/templates/no_limit/pdf/memio_vodic.html

Sadrzaj HTML/CSS dokumenta — POTPUNI WeasyPrint PDF, A4 format, 12-16 stranica:

Stil: toplo, moderno, ljubicasta i narancasta paleta (#7B2D8B ljubicasta, #FF6B35 narancasta, bijela)
Font: bez Google Fonts (WeasyPrint nema internet) — koristiti system-ui, Georgia, Arial

Struktura dokumenta (page-break-after: always za svaku stranicu):

STRANICA 1 — Naslovna
  Veliki naslov: "Tvoj ljubimac zaslužuje više od kartona u ladici"
  Podnaslov: "Besplatan digitalni putovni list za svakog ljubimca u Hrvatskoj"
  Logo tekst: memio.pet | NO LIMIT udruga
  Velika slika placeholder (sivi box s tekstom: [slika ljubimca])
  URL: memio.pet

STRANICA 2 — Problem
  Naslov: "Što se dogodi kad nestane putovnica?"
  3 paragrafa o gubitku dokumentacije, nemogucnosti pracenja vlasnistva,
  nestalim ljubimcima bez identiteta u azilima
  Konkretna prica: "Pas Rudi iz Osijeka — 3 azila, niti jedan zapis"

STRANICA 3 — Rjesenje
  Naslov: "memio.pet — digitalni putovni list za zivotni vijek"
  5 tocaka s ikonama (Unicode emoji u circles):
  📋 Medicinski karton doživotno
  🏠 Lanac vlasništva — tko je imao životinju
  📍 GPS povijest mjesta
  🔐 Blockchain verifikacija
  📱 QR kod na markici — instant pristup

STRANICA 4 — Prica Ljubete
  Naslov: "Ljubeta i njeni psi — kako je sve počelo"
  Osobna prica (fiktivna ali realna): uzgajivacnica, godinama papiri u ladicama,
  jedno stene prodano — i nestalo. Bez traga. Kupac se odjavio.
  "S memio.pet — to se ne moze desiti. Svaki pas ima svoj identitet."
  Foto placeholder za Ljubetu

STRANICA 5 — Kako radi (5 koraka)
  Naslov: "Registracija u 5 minuta"
  Numerirani koraci s opisom:
  1. Idi na memio.pet i registriraj uzgajivaliste
  2. Dodaj prvog ljubimca (ime, vrsta, datum rodenja)
  3. Unesi medicinski karton i povijest vlasnistva
  4. Naruci QR markicu (opcionalno, 5 EUR)
  5. Dijeli profil s kupcem — on preuzima evidenciju

STRANICA 6 — Za azile
  Naslov: "Za azile i skloništa — potpuno besplatno"
  Zasto besplatno: misija NO LIMIT udruge
  Sto dobivaju: digitalna evidencija svih zivotinja, pracenje usvajanja,
  izvjestaji za grad/zupaniju, smanjenje administracije 80%
  Citat (fiktivni): "Konacno ne trazimo papire po ladicama" — djelatnica azila, Slavonski Brod

STRANICA 7 — Javni poziv
  Naslov: "Pozovite vas azil da se pridruzi"
  Tekst javnog poziva — poziv gradovima, zupanijama, udrugama
  Upute: Prijavite se na no-limit.world/azili
  Forma QR kod placeholder
  Rok: trajno otvoreno

STRANICA 8 — Zasto NO LIMIT
  Naslov: "Tko stoji iza projekta"
  NO LIMIT udruga — misija, osnivaci, vrijednosti
  Veza s LIMIT Connect platformom — tech infrastruktura
  Transparentnost: open source, bez skrivenih troskova za azile

STRANICA 9 — Kontakt i zahvala
  Email: fina.connect.online@gmail.com
  Web: memio.pet | no-limit.world
  Adresa: Hrvatska
  "Hvala sto ste dio promjene"
  QR kodovi za obje stranice (placeholder boxes s labelama)

---

## KORAK 5 — View za PDF generaciju

READ: /var/www/fina-connect/no_limit/views.py

Dodaj dvije funkcije na kraj:

Funkcija 1 — download PDF:
def preuzmi_vodic(request):
    from core.pdf_utils import render_to_pdf
    pdf = render_to_pdf("no_limit/pdf/memio_vodic.html", {})
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="memio-pet-digitalna-zastita-zivotinja-2026.pdf"'
    return response

Funkcija 2 — HTML verzija za citanje online:
def vodic_online(request):
    return render(request, "no_limit/vodic_online.html", {})

Funkcija 3 — forma za prijavu azila:
def prijava_azila(request):
    from no_limit.models import AzilPrijava
    if request.method == "POST":
        naziv = request.POST.get("naziv", "").strip()
        email = request.POST.get("email", "").strip()
        grad = request.POST.get("grad", "").strip()
        poruka = request.POST.get("poruka", "").strip()
        if naziv and email and grad:
            AzilPrijava.objects.create(naziv=naziv, email=email, grad=grad, poruka=poruka)
            # WhatsApp notifikacija Ivanu
            try:
                from core.whatsapp import send_whatsapp
                send_whatsapp("+385XXXXXXXXX", f"Nov azil: {naziv}, {grad} ({email})")
            except Exception:
                pass
            return redirect("/no-limit/?prijava=ok")
    return redirect("/no-limit/")

---

## KORAK 6 — URL-ovi

READ: /var/www/fina-connect/no_limit/urls.py

Dodaj na kraj urlpatterns liste (append, ne replace!):
path("preuzmi-vodic/", views.preuzmi_vodic, name="preuzmi_vodic"),
path("vodic/", views.vodic_online, name="vodic_online"),
path("azili/prijava/", views.prijava_azila, name="prijava_azila"),

---

## KORAK 7 — vodic_online.html (HTML verzija za web)

WRITE: /var/www/fina-connect/no_limit/templates/no_limit/vodic_online.html

HTML stranica koja extenda base.html i prikazuje sadrzaj vodica kao web stranicu.
Ukljucuje:
- Isti sadrzaj kao PDF ali u web formatu
- Gumb "Preuzmi PDF" koji vodi na /no-limit/preuzmi-vodic/
- Forma za prijavu azila (POST na /no-limit/azili/prijava/)
- Meta OG tagovi za dijeljenje:
  og:title = "Digitalna zaštita ljubimaca — memio.pet"
  og:description = "Besplatan digitalni putovni list za svakog ljubimca u Hrvatskoj"
  og:url = "https://no-limit.world/vodic/"

---

## KORAK 8 — Finalna provjera

EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -3
EXEC: systemctl restart gunicorn-fina
EXEC: sleep 5 && curl -s -o /dev/null -w "HTTP %{http_code}" https://limit-connect.com/
EXEC: curl -s -o /dev/null -w "HTTP %{http_code}" https://no-limit.world/vodic/ 2>/dev/null || echo "URL jos ne radi - check urls.py"

EXEC: cd /var/www/fina-connect && git add -A && git commit -m "feat(no-limit): memio vodic PDF + javni poziv azilima + AzilPrijava model"

DONE kriterij:
- /no-limit/preuzmi-vodic/ vraca PDF (Content-Type: application/pdf)
- /no-limit/vodic/ vraca 200
- /no-limit/azili/prijava/ prima POST i sprema u DB
- manage.py check: 0 errors
- git commit postoji

---

## NAPOMENE ZA WHATSAPP BROJ:
Ivan — u views.py KORAK 5, funkcija prijava_azila:
send_whatsapp("+385XXXXXXXXX", ...) — zamijeni s pravim brojem iz .env
ili koristi: settings.IVAN_WHATSAPP_NUMBER ako postoji u settings.py


---

## DODATAK — MASKOTA AVIS (Boston Terrier)

Fotografije su na serveru u: /var/www/fina-connect/media/no_limit/maskota/
Fajlovi: Avis.jpeg, Avis2.jpeg, Avis3.jpeg

Ivan je platio autorska prava — slobodno koristiti u svim materijalima.

KORAK 0 (dodati PRIJE KORAKA 4):
Kopiraj slike u medije:
EXEC: cp /mnt/user-data/uploads/Avis*.jpeg /var/www/fina-connect/media/no_limit/maskota/ 2>/dev/null || echo "Kopiranje rucno — Ivan uploadira u /media/no_limit/maskota/"

Koristi slike u PDF templatu:
- Avis.jpeg → naslovna stranica (glavni portret, ozbiljan pogled)
- Avis2.jpeg → stranica 4 (Ljubetina prica — pas nauznak, veseo)
- Avis3.jpeg → stranica 9 (zahvala — Avis spava, miran)

U WeasyPrint HTML templatu koristiti:
<img src="{{ MEDIA_URL }}no_limit/maskota/Avis.jpeg" style="width:100%; border-radius:12px;">

MEDIA_URL u kontekstu:
from django.conf import settings
context["MEDIA_URL"] = settings.MEDIA_URL

