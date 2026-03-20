"""
partners/b2b_portal.py
════════════════════════════════════════════════════════════════════════════════
B2B Klijentski Portal — Sigurnosne funkcije

Pozivaju se iz portal_views.py i direktno u testovima.
Sve su pure functions — bez side effecta, lako testabilne.

  check_legal_vault_access(order)     → (ok, error_msg)
  validate_export_date_range(f, t)    → (ok, http_status, error_msg)
"""

import datetime

# ══════════════════════════════════════════════════════════════════════════════
# 8.2 — Legal Vault Access Control
# ══════════════════════════════════════════════════════════════════════════════

# Statusi u kojima je terenski protokol ZATVOREN (vozač je predao robu,
# potpisnica primljena) — Legal Vault smije biti dostupan
VAULT_ALLOWED_STATUSES = frozenset([
    'delivered',    # vozač potvrdio dostavu
    'completed',    # dispatcher zatvorio narudžbu
    'cancelled',    # otkazano — arhiva dostupna za evidenciju
])

# Statusi u kojima je roba u pokretu ili u obradi — Vault blokiran
VAULT_BLOCKED_STATUSES = frozenset([
    'pending',      # narudžba čeka potvrdu
    'confirmed',    # potvrđena, roba se priprema
    'picking',      # skladištar bira robu
    'packing',      # roba se pakira
    'in_transit',   # vozač je na putu — terenski protokol otvoren
    'loaded',       # utovareno na vozilo
])

VAULT_BLOCKED_MSG = (
    "Pristup dokazima omogucen je tek nakon zatvaranja terenskog protokola. "
    "Narudzba je trenutno u statusu '{status}'. "
    "Legal Vault bit ce dostupan kada vozac potvrdi dostavu i zatvori terenski protokol."
)


def check_legal_vault_access(order):
    """
    8.2: Provjeri je li Legal Vault dostupan za ovu narudžbu.

    Legal Vault (forenzika: potpisi, reklamacije, temperaturni lanac)
    smije biti dostupan ISKLJUČIVO nakon što je terenski protokol zatvoren
    (status: delivered / completed).

    Args:
        order: MarketplaceOrder instanca (ili mock s .status atributom)

    Returns:
        (ok: bool, error_message: str)

    Primjer:
        ok, err = check_legal_vault_access(order)
        if not ok:
            return JsonResponse({"error": err}, status=403)
    """
    status = getattr(order, "status", "")

    if status in VAULT_ALLOWED_STATUSES:
        return True, ""

    # Eksplicitno blokirani statusi
    if status in VAULT_BLOCKED_STATUSES:
        return False, VAULT_BLOCKED_MSG.format(status=status)

    # Nepoznati status — sigurnosni default: blokiraj
    return False, VAULT_BLOCKED_MSG.format(status=("nepoznat: %s" % status))


# ══════════════════════════════════════════════════════════════════════════════
# 8.3 — Bulk Export Date Range Validation (anti-DDoS)
# ══════════════════════════════════════════════════════════════════════════════

MAX_EXPORT_DAYS = 31  # Maksimalni dozvoljeni raspon u danima


def validate_export_date_range(date_from, date_to):
    """
    8.3: Validacija raspona datuma za bulk ZIP export.

    Blokira:
      - None datume → HTTP 400 Bad Request
      - Obrnuti raspon (from > to) → HTTP 400 Bad Request
      - Raspon > 31 dan → HTTP 413 Payload Too Large

    Args:
        date_from: datetime.date | None
        date_to:   datetime.date | None

    Returns:
        (ok: bool, http_status: int, error_message: str)

    Primjer u view-u:
        ok, status, err = validate_export_date_range(date_from, date_to)
        if not ok:
            return JsonResponse({"error": err}, status=status)
    """
    # Provjera None
    if date_from is None or date_to is None:
        return False, 400, (
            "Datumi su obavezni. Navedite date_from i date_to u formatu YYYY-MM-DD."
        )

    # Provjera tipova
    if not isinstance(date_from, datetime.date) or not isinstance(date_to, datetime.date):
        return False, 400, "Neispravni format datuma. Koristite YYYY-MM-DD."

    # Obrnuti raspon
    if date_from > date_to:
        return False, 400, (
            "Neispravan raspon: date_from (%s) je kasniji od date_to (%s)."
            % (date_from.isoformat(), date_to.isoformat())
        )

    # Provjera duljine raspona
    delta = (date_to - date_from).days  # razlika u danima; 31 = Jan1→Feb1 (granica)
    if delta > MAX_EXPORT_DAYS:
        return False, 413, (
            "Raspon od %d dana premasuje maksimalni dozvoljeni raspon od %d dana (razlika). "
            "Smanjite raspon ili koristite vise odvojenih zahtjeva. "
            "Anti-DDoS zastita aktivna." % (delta, MAX_EXPORT_DAYS)
        )

    return True, 200, ""
