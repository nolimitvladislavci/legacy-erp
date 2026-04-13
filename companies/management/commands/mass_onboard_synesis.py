import csv
import os

from django.core.management.base import BaseCommand

from companies.models import Company
from partners.models import Partner
from synesis.models import SynesisConfig


class Command(BaseCommand):
    help = "Masovni uvoz firmi pod umbrella. Dva moda: --from-partners ili --from-csv"

    def add_arguments(self, parser):
        parser.add_argument("--umbrella-oib", type=str, required=True, help="OIB umbrella tvrtke (npr. Konjik d.o.o.)")
        parser.add_argument(
            "--from-partners", action="store_true", help="Kreiraj Company zapise iz postojecih Partner records"
        )
        parser.add_argument("--from-csv", type=str, default="", help="Putanja do CSV datoteke (name,oib,city,address)")
        parser.add_argument(
            "--synesis-base",
            type=str,
            default=r"C:\Synesis",
            help="Windows bazna putanja za Synesis MDB (default: C:\\Synesis)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Samo prikazi sto bi se napravilo, bez pisanja u bazu"
        )
        parser.add_argument(
            "--relation",
            type=str,
            default="client",
            choices=["client", "subsidiary", "franchise"],
            help="Tip umbrella veze (default: client)",
        )

    def handle(self, *args, **options):
        umbrella_oib = options["umbrella_oib"]
        dry_run = options["dry_run"]
        relation = options["relation"]
        synesis_base = options["synesis_base"]

        # 1. Find umbrella parent
        try:
            parent = Company.objects.get(oib=umbrella_oib)
        except Company.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Tvrtka s OIB-om {umbrella_oib} ne postoji."))
            return

        if not parent.is_umbrella:
            parent.is_umbrella = True
            if not dry_run:
                parent.save(update_fields=["is_umbrella"])
            self.stdout.write(f"Postavljam {parent.name} kao umbrella.")

        self.stdout.write(self.style.SUCCESS(f"Umbrella: {parent.name} (OIB: {parent.oib})"))

        # 2. Collect firms to import
        firms = []  # list of dicts: name, oib, city, address

        if options["from_partners"]:
            self.stdout.write("\nMod: FROM PARTNERS")
            existing_oibs = set(Company.objects.values_list("oib", flat=True))
            existing_oibs.discard("")
            partners = (
                Partner.objects.filter(company=parent).exclude(oib="").exclude(oib__in=existing_oibs).order_by("name")
            )
            self.stdout.write(f"Partneri za uvoz: {partners.count()}")
            for p in partners:
                firms.append(
                    {
                        "name": p.name,
                        "oib": p.oib,
                        "city": getattr(p, "city", ""),
                        "address": getattr(p, "address", ""),
                    }
                )

        elif options["from_csv"]:
            csv_path = options["from_csv"]
            self.stdout.write(f"\nMod: FROM CSV ({csv_path})")
            if not os.path.exists(csv_path):
                self.stderr.write(self.style.ERROR(f"CSV ne postoji: {csv_path}"))
                return
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    firms.append(
                        {
                            "name": row.get("name", row.get("naziv", "")),
                            "oib": row.get("oib", ""),
                            "city": row.get("city", row.get("grad", "")),
                            "address": row.get("address", row.get("adresa", "")),
                        }
                    )
            self.stdout.write(f"Firmi u CSV-u: {len(firms)}")
        else:
            self.stderr.write(self.style.ERROR("Morate koristiti --from-partners ili --from-csv"))
            return

        if not firms:
            self.stdout.write("Nema firmi za uvoz.")
            return

        # 3. Import loop
        created = 0
        skipped = 0
        bat_scripts = []

        for firm in firms:
            name = firm["name"].strip()
            oib = firm["oib"].strip()

            if not name:
                continue

            # Skip if company with this OIB already exists
            if oib and Company.objects.filter(oib=oib).exists():
                self.stdout.write(f"  SKIP {name} (OIB {oib} vec postoji)")
                skipped += 1
                continue

            # Skip if same name already under this umbrella
            if Company.objects.filter(name__iexact=name, umbrella_parent=parent).exists():
                self.stdout.write(f"  SKIP {name} (vec pod umbrella)")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY] Kreirao bi: {name} | {oib}")
                created += 1
                continue

            # Create company
            new_co = Company.objects.create(
                name=name,
                oib=oib,
                city=firm.get("city", ""),
                address=firm.get("address", ""),
                umbrella_parent=parent,
                umbrella_relation=relation,
                is_umbrella=False,
                subscription_plan="free",
            )

            # Create SynesisConfig with Windows paths
            safe_name = name.replace(" ", "_").replace(".", "")[:30]
            storage_path = f"{synesis_base}\\{safe_name}\\Storage.mdb"
            journal_path = f"{synesis_base}\\{safe_name}\\Journal.mdb"

            config = SynesisConfig.objects.create(
                company=new_co,
                storage_db_path=storage_path,
                journal_db_path=journal_path,
            )

            bat_scripts.append(
                {
                    "name": safe_name,
                    "token": config.api_token,
                    "storage": storage_path,
                }
            )

            created += 1
            self.stdout.write(self.style.SUCCESS(f"  + {name} | OIB: {oib} | Token: {config.api_token[:12]}..."))

        # 4. Summary
        self.stdout.write("")
        self.stdout.write("=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Kreirano: {created} | Preskoceno: {skipped}"))
        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(f"{prefix}Umbrella {parent.name} sada ima {parent.umbrella_children.count()} djece.")

        # 5. Generate master BAT script
        if bat_scripts and not dry_run:
            bat_dir = os.path.join("/var/www/fina-connect/media/synesis_bat/")
            os.makedirs(bat_dir, exist_ok=True)
            master_bat = os.path.join(bat_dir, f"sync_all_{parent.oib}.bat")

            lines = [
                "@echo off",
                f"REM Master sync za {parent.name}",
                f"REM Generirano automatski - {created} firmi",
                "REM Pokreni ovo na Windows racunalu gdje su Synesis baze",
                "",
                "set SERVER=https://viskovic-group.de",
                "",
            ]

            for bs in bat_scripts:
                lines.append(f"echo Syncing {bs['name']}...")
                lines.append(f'cscript //nologo sync_mdb.vbs "{bs["storage"]}" "{bs["token"]}" %SERVER%')
                lines.append("")

            lines.append("echo.")
            lines.append(f"echo GOTOVO! Syncirano {len(bat_scripts)} firmi.")
            lines.append("pause")

            with open(master_bat, "w", encoding="utf-8") as f:
                f.write("\r\n".join(lines))

            self.stdout.write(self.style.SUCCESS(f"\nMaster BAT: {master_bat}"))
            self.stdout.write("Downloadajte ga i pokrenite na Windows racunalu gdje su Synesis MDB baze.")
