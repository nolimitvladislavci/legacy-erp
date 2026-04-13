from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
"""
delivery/warehouse_safety.py
════════════════════════════════════════════════════════
Centralne sigurnosne provjere za Pick & Pack terminal.

Sve su 'pure functions' (nema side effecta) — lako testabilne.

Sigurnosni slojevi:
  6.1 _check_fefo         — FEFO redosljed šarži (First Expired First Out)
  6.2 _check_weight_tolerance — IoT vaga tolerancija ±20%
  6.3 _check_anti_crush   — zabrana teških artikala iznad krhkih
  6.4 genesis_scan_lock   — provjera IFCO ambalaže pri zaključavanju narudžbe

Import u warehouse_views.py:
  from .warehouse_safety import _check_fefo, _check_weight_tolerance, _check_anti_crush
"""
import datetime
from decimal import Decimal

# ── Konstante ─────────────────────────────────────────────────────────────────
WEIGHT_TOLERANCE = Decimal('0.20')  # ±20% dozvoljena devijacija


# ══════════════════════════════════════════════════════════════════════════════
# 6.1 FEFO — First Expired First Out
# ══════════════════════════════════════════════════════════════════════════════

def _check_fefo(product, scanned_expiry, oldest_available):
    """
    FEFO: Zabrana skeniranja novije šarže dok postoji starija (raniji rok).

    Args:
        product:          MarketplaceProduct — za naziv u poruci greške
        scanned_expiry:   datetime.date — rok trajanja skenirane šarže
        oldest_available: datetime.date | None — najstariji rok u sustavu

    Returns:
        (ok: bool, error_message: str)

    Primjer u API-ju:
        oldest = MarketplaceProduct.get_oldest_batch_expiry(product, company)
        ok, err = _check_fefo(product, scanned_expiry=batch_date, oldest_available=oldest)
    """
    if oldest_available is None:
        # Nema starije šarže u sustavu — sken je ok
        return True, ''

    if scanned_expiry > oldest_available:
        return False, (
            'FEFO BLOKADA: Proizvod "%s" ima stariju sarzu '
            '(rok: %s). '
            'Skenirani rok (%s) nije najstariji. '
            'Potrebno je uzeti sarzu s ranijim rokom trajanja.'
            % (
                product.name,
                oldest_available.strftime('%d.%m.%Y'),
                scanned_expiry.strftime('%d.%m.%Y'),
            )
        )
    return True, ''


# ══════════════════════════════════════════════════════════════════════════════
# 6.2 IoT Vaga — Weight Tolerance
# ══════════════════════════════════════════════════════════════════════════════

def _check_weight_tolerance(actual_qty, ordered_qty):
    """
    IoT Vaga: Blokada unosa koji odstupa više od ±20% od naručene količine.

    Args:
        actual_qty:  Decimal — izmjerena količina s vage
        ordered_qty: Decimal — naručena količina

    Returns:
        (ok: bool, error_message: str)
    """
    if ordered_qty <= 0:
        return True, ''
    deviation = abs(actual_qty - ordered_qty) / ordered_qty
    if deviation > WEIGHT_TOLERANCE:
        pct = int(deviation * 100)
        return False, (
            'Tolerancija premasena: %s vs naruceno %s '
            '(%d%% odstupanje, max %d%%). '
            'Koristite "force=1" za override.'
            % (actual_qty, ordered_qty, pct, int(WEIGHT_TOLERANCE * 100))
        )
    return True, ''


# ══════════════════════════════════════════════════════════════════════════════
# 6.3 Anti-Crush — Heavy over Fragile
# ══════════════════════════════════════════════════════════════════════════════

def _check_anti_crush(rollwagen, new_product):
    """
    Anti-Crush: Teški artikli ne smiju u rollwagen koji već sadrži krhke.

    Args:
        rollwagen:    Rollwagen instanca (s bound_order)
        new_product:  MarketplaceProduct koji se skenira

    Returns:
        (ok: bool, error_message: str)
    """
    if not new_product.is_heavy:
        return True, ''

    if not rollwagen.bound_order:
        return True, ''

    fragile_in_rw = rollwagen.bound_order.items.filter(
        product__is_fragile=True,
        packed_at__isnull=False,
    ).exists()

    if fragile_in_rw:
        return False, (
            'ANTI-CRUSH BLOKADA: Rollwagen %s vec sadrzi krhke proizvode. '
            'Teske stavke (%s) ne mogu ici u isti rollwagen.'
            % (rollwagen.qr_code, new_product.name)
        )
    return True, ''


# ══════════════════════════════════════════════════════════════════════════════
# 6.4 Genesis Scan — IFCO Packaging Lock
# ══════════════════════════════════════════════════════════════════════════════

def _check_genesis_packaging(rollwagen, required_ifco_count=1):
    """
    Genesis Scan: Blokada zaključavanja narudžbe dok se ne zaduži
    točan broj IFCO ambalaže.

    Args:
        rollwagen:           Rollwagen s packaging_count JSON poljem
        required_ifco_count: minimalni broj IFCO-a koji mora biti skeniran

    Returns:
        (ok: bool, error_message: str)
    """
    packaging = rollwagen.packaging_count or {}
    ifco_scanned = packaging.get('ifco', 0)

    if ifco_scanned < required_ifco_count:
        return False, (
            'GENESIS SCAN BLOKADA: Rollwagen %s — skenirano %d IFCO '
            '(potrebno minimum %d). '
            'Skenirajte ambalazu prije zaključavanja narudzbe.'
            % (rollwagen.qr_code, ifco_scanned, required_ifco_count)
        )
    return True, ''
