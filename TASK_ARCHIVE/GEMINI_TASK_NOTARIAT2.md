GEMINI TASK: Notariat Sprint 2 — PDF predlosci + Admin + Dimnjacari template
Datum: 03.04.2026. Rok: 05.04.2026.
PRAVILO: Ne pisi nijedan code block s backtickovima. Nema ```. Samo READ WRITE EXEC akcije.

KONTEKST — sto je vec gotovo:
- notariat/ app postoji s modelima PravniPredmet, DimnjacarskaInspekcija, NotariatPredlozak
- Migracija 0001_notariat_init primijenjena
- notariat/views.py ima pravnik_dashboard i dimnjacari_dashboard
- notariat/urls.py postoji
- notariat/templates/notariat/pravnik_dashboard.html postoji
- CroValidator API radi na /api/v1/validate/

KORAK 1 - Provjeri stanje
EXEC: cd /var/www/fina-connect && ls notariat/templates/notariat/
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | tail -5

KORAK 2 - Kreiraj dimnjacari_dashboard.html
Lokacija: notariat/templates/notariat/dimnjacari_dashboard.html
WRITE sadrzaj koji extends base.html, ima f-container, f-hero s naslovom Dimnjacarski pregledi i ikonom vatre, blok za sljedece preglede u 30 dana (f-card f-card-gold), i tablicu svih inspekcija s kolonama Adresa, Dimnjak, Status (badge zeleni/zuti/crveni), Datum pregleda, Sljedeci pregled. Koristi Django template tags bez code fences.

KORAK 3 - Registriraj modele u admin
WRITE notariat/admin.py s importom modela i registracijom sva tri modela. NotariatPredlozak list_display vrsta naslov aktivan. PravniPredmet list_display naziv vrsta status rok klijent, list_filter status vrsta, search_fields naziv. DimnjacarskaInspekcija list_display adresa broj_dimnjaka status_dimnjaka datum_pregleda sljedeci_pregled, list_filter status_dimnjaka, search_fields adresa.

KORAK 4 - Kreiraj direktorij za PDF predloske
EXEC: mkdir -p /var/www/fina-connect/notariat/templates/notariat/pdf

KORAK 5 - Provjeri kako WeasyPrint radi u projektu
EXEC: cd /var/www/fina-connect && grep -n "WeasyPrint\|weasyprint\|HTML(" invoicing/services/pdf_service.py | head -10
EXEC: cd /var/www/fina-connect && head -30 invoicing/templates/invoicing/invoice_hr_datev.html

KORAK 6 - Kreiraj PDF predlozak za Potvrdu o ispravnosti dimnjaka
Lokacija: notariat/templates/notariat/pdf/potvrda_dimnjaka.html
Ovaj template je standalone HTML za WeasyPrint (ne extends base.html).
Style blok na pocetku: page size A4 margin 20mm. Font DejaVu Sans Arial 10pt. Header sa nazivom firme i naslovom POTVRDA O ISPRAVNOSTI DIMNJAKA. Zakonska osnova tekst: Sukladno Zakonu o obavljanju dimnjacarskih poslova (NN 103/15). Tijelo s Django varijablama inspekcija.adresa, inspekcija.broj_dimnjaka, inspekcija.datum_pregleda, inspekcija.get_status_dimnjaka_display, inspekcija.opis_nalaza, inspekcija.preporuke, inspekcija.sljedeci_pregled. Footer: Dokument generiran u LIMIT Connect sustavu. SHA-256 kontrolni broj i inspekcija.pdf_sha256. Mjesto za potpis dimnjacara i pecat.

KORAK 7 - Kreiraj PDF predlozak za Punomoc (opunomocenje)
Lokacija: notariat/templates/notariat/pdf/punomoc.html
Standalone HTML za WeasyPrint. Naslov: PUNOMOC (OPUNOMOCENJE). Zakonska osnova: Zakon o obveznim odnosima (NN 35/05). Tijelo s varijablama vlastodavac_ime, vlastodavac_oib, opunomocenik_ime, opunomocenik_oib, opseg_ovlasti, trajanje, datum. Napomena: Za pravnu valjanost potrebna je ovjera javnog biljeznika.

KORAK 8 - Dodaj generate_pdf view u notariat/views.py
READ: /var/www/fina-connect/notariat/views.py
WRITE: dodaj na kraj views.py import HttpResponse i funkciju generate_dimnjak_pdf koja prima request i inspekcija_id, ucitava DimnjacarskaInspekcija objekt za company, renderira template notariat/pdf/potvrda_dimnjaka.html s kontekstom inspekcija i company, generira PDF putem WeasyPrint HTML(string=html_string).write_pdf(), vraca HttpResponse s content_type application/pdf i header Content-Disposition attachment filename potvrda_dimnjaka_{inspekcija.pk}.pdf. Takoer izracunaj SHA-256 hash PDF bytova i spremi u inspekcija.pdf_sha256.

KORAK 9 - Dodaj URL za PDF generaciju
READ: /var/www/fina-connect/notariat/urls.py
WRITE: dodaj path dimnjacari/inspekcija-pdf/int-pk-slash na views.generate_dimnjak_pdf s imenom generate_dimnjak_pdf.

KORAK 10 - Tarifa kalkulator
Lokacija: notariat/tarifa.py
WRITE novi fajl s Python recnikom TARIFE koji sadrzi kljuceve punomoc osnivanje_jdoo osnivanje_doo zaduznica pregled_dimnjaka potvrda_dimnjaka. Za punomoc osnova 10.00 pdv True. Za osnivanje_jdoo osnova 50.00 pdv True. Za osnivanje_doo osnova 100.00 pdv True. Za zaduznica postotak 0.001 minimum 10.00 maximum 200.00 pdv True. Za pregled_dimnjaka osnova 15.00 pdv True. Za potvrda_dimnjaka osnova 5.00 pdv True. Takoer napiši funkciju izracunaj_tarifu koja prima vrsta string i vrijednost_eur float s defaultom 0, vraca dict s kljucevima nagrada pristojba pdv_iznos ukupno kao Decimal vrijednosti.

KORAK 11 - Django check i collectstatic
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1 | grep -E "ERROR|System check" | head -10
EXEC: cd /var/www/fina-connect && venv/bin/python manage.py collectstatic --noinput 2>&1 | tail -3

KORAK 12 - Git commit
EXEC: cd /var/www/fina-connect && git add notariat/ && git commit -m "feat(notariat): dimnjacari template + admin + PDF potvrda + punomoc + tarifa kalkulator"

KORAK 13 - Restart
EXEC: systemctl restart gunicorn-fina

KORAK 14 - Verifikacija
EXEC: curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/notariat/pravnik/ -H "Host: limit-connect.com"
EXEC: cd /var/www/fina-connect && venv/bin/python -c "from notariat.tarifa import izracunaj_tarifu; print(izracunaj_tarifu('punomoc'))"

DONE kriterij:
- dimnjacari_dashboard.html postoji
- notariat/admin.py registrira sva tri modela
- notariat/templates/notariat/pdf/potvrda_dimnjaka.html postoji
- notariat/templates/notariat/pdf/punomoc.html postoji
- notariat/tarifa.py postoji s izracunaj_tarifu funkcijom
- Gunicorn restartovan bez greske
- git commit napravljen
