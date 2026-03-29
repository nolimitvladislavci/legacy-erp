
# One-time: extract cert metadata za sve postojeće FiscalConfig-e
from fiskalizacija.models import FiscalConfig
for fc in FiscalConfig.objects.filter(cert_expires_at__isnull=True):
    fc.extract_cert_metadata()
    if fc.cert_expires_at:
        print(f'  Extracted: {fc.company.name} → expires {fc.cert_expires_at}, subject={fc.cert_subject[:40]}')
    else:
        print(f'  Skip: {fc.company.name} — no cert or error')
