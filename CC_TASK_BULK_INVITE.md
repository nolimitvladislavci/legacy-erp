# CC Task — bulk_invite management command

Tvoj zadatak je jedan fajl, jedna komanda, jedan cilj.
Rok: danas. Dry-run mora proći bez grešaka.

---

## ŠTO RADIŠ

Kreiraš management command:
  `/var/www/fina-connect/core/management/commands/bulk_invite.py`

Komanda se pokreće kao:
  `cd /var/www/fina-connect && venv/bin/python manage.py bulk_invite --dry-run`
  `cd /var/www/fina-connect && venv/bin/python manage.py bulk_invite --company "Konjik"`
  `cd /var/www/fina-connect && venv/bin/python manage.py bulk_invite`

---

## KORAK 0 — ČITAJ PRVO, PIŠI POSLIJE (obavezno)

Prije nego napišeš ijedan red koda, pročitaj ova tri fajla:

```
cat /var/www/fina-connect/templates/email/welcome_onboarding.html
```
→ Zapamti SVE varijable oblika {{ nesto }}

```
cat /var/www/fina-connect/core/email_tasks.py
```
→ Koristit ćeš send_html_email_task — vidi potpis funkcije

```
grep -n "must_change_password\|related_name\|company" /var/www/fina-connect/accounts/models.py | head -30
```
→ Provjeri točan related_name za profile

---

## LOGIKA KOMANDE

```python
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.conf import settings
import secrets, string

class Command(BaseCommand):
    help = "Pošalji welcome email svim korisnicima koji se nikad nisu prijavili"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--company", type=str, default=None)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        company_filter = options["company"]

        from registration.models import CompanySubscription
        from core.email_tasks import send_html_email_task

        subs = CompanySubscription.objects.filter(is_active=True).select_related("company")
        if company_filter:
            subs = subs.filter(company__name__icontains=company_filter)

        total = 0
        for sub in subs:
            company = sub.company
            # Korisnici koji NIKAD nisu ušli
            users = User.objects.filter(
                profile__company=company,   # ← provjeri related_name u accounts/models.py
                last_login__isnull=True,
                is_active=True,
            ).select_related("profile")

            count = users.count()
            self.stdout.write(f"
Kompanija: {company.name} — {count} korisnika")

            for user in users:
                # Temp lozinka
                chars = string.ascii_letters + string.digits
                temp_pass = "".join(secrets.choice(chars) for _ in range(12))

                if not dry_run:
                    # Postavi lozinku
                    user.set_password(temp_pass)
                    user.save(update_fields=["password"])

                    # Postavi must_change_password
                    profile = user.profile
                    profile.must_change_password = True
                    profile.save(update_fields=["must_change_password"])

                    # Render email
                    html_body = render_to_string(
                        "email/welcome_onboarding.html",
                        {
                            "user_name": user.get_full_name() or user.username,
                            "company_name": company.name,
                            "username": user.username,
                            "temp_password": temp_pass,
                            "login_url": "https://limit-connect.com/hr/accounts/login/",
                        },
                    )
                    text_body = (
                        f"Dobrodošli u LIMIT Connect!
"
                        f"Korisničko ime: {user.username}
"
                        f"Privremena lozinka: {temp_pass}
"
                        f"Prijava: https://limit-connect.com/hr/accounts/login/"
                    )

                    if user.email:
                        send_html_email_task.delay(
                            subject=f"Dobrodošli u LIMIT Connect — {company.name}",
                            text_body=text_body,
                            html_body=html_body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email],
                        )
                        self.stdout.write(self.style.SUCCESS(f"  ✅ {user.username} ({user.email})"))
                    else:
                        self.stdout.write(self.style.WARNING(f"  ⚠️  {user.username} — nema email"))
                else:
                    status = f"({user.email})" if user.email else "(BEZ EMAILA)"
                    self.stdout.write(f"  [DRY RUN] {user.username} {status}")

                total += 1

        marker = "[DRY RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"
{marker}UKUPNO: {total} korisnika"))
```

---

## TESTIRANJE (obavezni koraci redom)

**Korak 1 — Django check:**
```bash
cd /var/www/fina-connect && venv/bin/python manage.py check 2>&1
```
Mora biti: `System check identified no issues`

**Korak 2 — Dry-run:**
```bash
cd /var/www/fina-connect && venv/bin/python manage.py bulk_invite --dry-run 2>&1
```
Mora prikazati kompanije i korisnike BEZ grešaka.

**Korak 3 — Filter test:**
```bash
cd /var/www/fina-connect && venv/bin/python manage.py bulk_invite --dry-run --company "Konjik" 2>&1
```
Mora prikazati samo Konjik korisnike.

---

## NAJČEŠĆE GREŠKE — izbjegni

❌ `profile__company` — provjeri related_name u accounts/models.py, možda je drugačiji  
❌ `send_html_email_task(...)` bez `.delay()` — mora biti async  
❌ Ne provjeravaj `user.email` → može biti prazan string, ne samo None  
❌ Ne diraj korisnike koji imaju `last_login__isnull=False`  

---

## KADA ZAVRŠIŠ

Napiši Ivanu:
- Dry-run output (copy-paste)  
- Broj korisnika po kompaniji  
- Broj korisnika bez emaila (⚠️)  

Ivan odlučuje kad ide pravo slanje. Ti ne pokrećeš bez `--dry-run` dok Ivan ne kaže.

