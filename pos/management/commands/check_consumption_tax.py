"""
Provjera: koje tvrtke s NKD 56.xx (ugostiteljstvo) nemaju aktiviran
porez na potrošnju. Zakon o lokalnim porezima NN 115/16, čl.20-22.
"""
from django.core.management.base import BaseCommand
from companies.models import Company


class Command(BaseCommand):
    help = "Provjeri ugostiteljske tvrtke bez aktivnog poreza na potrošnju"

    def handle(self, *args, **options):
        # NKD 56.xx = Djelatnosti pripreme i usluživanja hrane i pića
        ugostitelji = Company.objects.filter(
            nkd_code__code__startswith='56'
        ).select_related('nkd_code')

        if not ugostitelji.exists():
            self.stdout.write("Nema tvrtki s NKD 56.xx u sustavu.")
            return

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("  POREZ NA POTROŠNJU — Provjera obveznika")
        self.stdout.write(f"{'='*60}\n")

        missing = []
        ok = []

        for c in ugostitelji:
            try:
                ps = c.pos_settings
                if ps.consumption_tax_active:
                    ok.append(c)
                else:
                    missing.append(c)
            except Exception:
                missing.append(c)

        for c in ok:
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {c.name} (NKD {c.nkd_code.code}) — PP aktiviran"
            ))

        for c in missing:
            nkd = c.nkd_code.code if c.nkd_code else '?'
            self.stdout.write(self.style.WARNING(
                f"  ⚠ {c.name} (NKD {nkd}) — PP NIJE aktiviran!"
            ))

        self.stdout.write(f"\n  Ukupno: {len(ok)} OK, {len(missing)} nedostaje")
        if missing:
            self.stdout.write(self.style.WARNING(
                "\n  PREPORUKA: Aktivirajte PP za gore navedene tvrtke "
                "u POS Postavke → Porez na potrošnju"
            ))
