"""
core/qr_registry.py — Globalni QR Registry servis

Jedina točka za kreiranje i dohvaćanje QR tokena u sustavu.
Auto-prikvačuje W3C Verifiable Credential + viral code pri kreiranju.

Korištenje:
    from core.qr_registry import get_or_create_qr, qr_verify_url

    qr = get_or_create_qr("arhiva.entry", str(entry.id), label="Račun HR-2026-0042")
    url = qr.verify_url   # /qr/<token>/
"""

import hashlib
import logging
import secrets
from datetime import datetime
from datetime import timezone as _tz

logger = logging.getLogger("fenix.qr_registry")


# ── Verifiable Credential (W3C VC 1.1 — Budućnost 1) ───────────────────────


def build_vc_payload(
    object_type: str,
    object_ref: str,
    label: str,
    company_name: str,
    token: str,
    chain_hash: str = "",
) -> dict:
    """
    W3C Verifiable Credential 1.1 payload.
    Embeddira se u QR i dostupan je offline skeniranjem.

    Spec: https://www.w3.org/TR/vc-data-model/
    """
    now_iso = datetime.now(_tz.utc).isoformat()
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1", "https://fenix.limit-connect.com/ns/qr-registry/v1"],
        "type": ["VerifiableCredential", "FenixDocumentCredential"],
        "id": f"https://fina-connect.online/qr/{token}/",
        "issuer": {"id": "https://fina-connect.online", "name": "LIMIT Connect — Fenix ERP"},
        "issuanceDate": now_iso,
        "credentialSubject": {
            "id": f"urn:fenix:{object_type}:{object_ref}",
            "type": object_type,
            "ref": object_ref,
            "label": label,
            "issuerCompany": company_name,
            "documentHash": chain_hash,
            "verifyUrl": f"https://fina-connect.online/qr/{token}/",
        },
        "proof": {
            "type": "FenixHMAC2026",
            "created": now_iso,
            "proofValue": hashlib.sha256(f"{token}:{object_type}:{object_ref}:{chain_hash}".encode()).hexdigest()[:32],
        },
    }


# ── Viral code generator (Budućnost 3) ──────────────────────────────────────


def _gen_viral_code(token: str) -> str:
    """Kratki referral kod: FX + 6 alfanumerika."""
    suffix = secrets.token_urlsafe(5)[:6].upper()
    return f"FX{suffix}"


# ── Glavni API ───────────────────────────────────────────────────────────────


def get_or_create_qr(
    object_type: str,
    object_ref: str,
    label: str = "",
    company_name: str = "",
    created_by: str = "",
    chain_hash: str = "",
    expires_at=None,
) -> "QRToken":
    """
    Idempotentno dohvati ili kreiraj QRToken za dati objekt.

    Args:
        object_type: npr. "arhiva.entry", "invoicing.invoice"
        object_ref:  UUID/PK objekta kao string
        label:       Kratki opis za verify stranicu
        company_name: Naziv firme (denormaliziran)
        created_by:  Username ili "system"
        chain_hash:  SHA-256 hash za VC (opcijalno)
        expires_at:  datetime ili None (trajno)

    Returns:
        QRToken instanca (nova ili postojeća)
    """
    from core.qr_registry_models import QRToken

    qr, created = QRToken.objects.get_or_create(
        object_type=object_type,
        object_ref=str(object_ref),
        defaults={
            "label": label[:200],
            "company_name": company_name[:200],
            "created_by": created_by[:100],
            "expires_at": expires_at,
        },
    )

    if created:
        # Generiraj VC + viral code
        qr.vc_payload = build_vc_payload(
            object_type=object_type,
            object_ref=str(object_ref),
            label=label,
            company_name=company_name,
            token=qr.token,
            chain_hash=chain_hash,
        )
        qr.viral_code = _gen_viral_code(qr.token)
        qr.save(update_fields=["vc_payload", "viral_code"])
        logger.info("QRToken created: %s → %s:%s", qr.short, object_type, object_ref[:20])

    return qr


def qr_verify_url(object_type: str, object_ref: str) -> str:
    """
    Brzo dohvati verify URL bez kreiranja (None ako ne postoji).
    """
    from core.qr_registry_models import QRToken

    try:
        qr = QRToken.objects.only("token").get(object_type=object_type, object_ref=str(object_ref))
        return qr.verify_url
    except QRToken.DoesNotExist:
        return ""


# ── Tamper Alert (Budućnost 2) ───────────────────────────────────────────────


def send_tamper_alert_async(qr_token_id: str) -> None:
    """Pokretač Celery taska za tamper alert."""
    try:
        from core.qr_registry_tasks import send_tamper_alert_task

        send_tamper_alert_task.apply_async(args=[qr_token_id])
    except Exception as e:
        logger.warning("Tamper alert task failed: %s", e)


# ── Signal connectori ────────────────────────────────────────────────────────


def _connect_signals() -> None:
    """
    Povežu Django signale za auto-generiranje QR kod kreiranja/spašavanja objekta.
    Poziva se iz QRRegistryConfig.ready().
    """
    from django.db.models.signals import post_save

    # Arhiva Entry
    try:
        from documents.models import ArhivaEntry

        post_save.connect(
            _on_arhiva_entry_save, sender=ArhivaEntry, weak=False, dispatch_uid="qr_registry_arhiva_entry"
        )
    except ImportError:
        pass

    # Invoice
    try:
        from invoicing.models import Invoice

        post_save.connect(_on_invoice_save, sender=Invoice, weak=False, dispatch_uid="qr_registry_invoice")
    except ImportError:
        pass

    # POS Receipt
    try:
        from pos.models import Receipt

        post_save.connect(_on_pos_receipt_save, sender=Receipt, weak=False, dispatch_uid="qr_registry_pos_receipt")
    except ImportError:
        pass

    # NO LIMIT Member
    try:
        from no_limit.models import Member

        post_save.connect(
            _on_no_limit_member_save, sender=Member, weak=False, dispatch_uid="qr_registry_no_limit_member"
        )
    except ImportError:
        pass

    logger.debug("QR Registry signals connected")


def _on_arhiva_entry_save(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        company_name = getattr(instance.company, "name", "")
        get_or_create_qr(
            "arhiva.entry",
            str(instance.id),
            label=instance.title or "Arhiva dokument",
            company_name=company_name,
            chain_hash=instance.layer1_sha256 or "",
        )
    except Exception as e:
        logger.warning("QR gen failed for ArhivaEntry %s: %s", instance.id, e)


def _on_invoice_save(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        company_name = getattr(instance.company, "name", "")
        label = getattr(instance, "invoice_number", None) or f"Račun #{instance.pk}"
        get_or_create_qr(
            "invoicing.invoice",
            str(instance.pk),
            label=label,
            company_name=company_name,
        )
    except Exception as e:
        logger.warning("QR gen failed for Invoice %s: %s", instance.pk, e)


def _on_pos_receipt_save(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        company_name = getattr(instance.company, "name", "") if hasattr(instance, "company") else ""
        get_or_create_qr(
            "pos.receipt",
            str(instance.pk),
            label=f"POS isječak #{instance.pk}",
            company_name=company_name,
        )
    except Exception as e:
        logger.warning("QR gen failed for POS Receipt %s: %s", instance.pk, e)


def _on_no_limit_member_save(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        full_name = getattr(instance, "full_name", None) or str(instance)
        get_or_create_qr(
            "no_limit.member",
            str(instance.pk),
            label=f"NO LIMIT član: {full_name}",
            company_name="NO LIMIT udruga",
        )
    except Exception as e:
        logger.warning("QR gen failed for NO LIMIT Member %s: %s", instance.pk, e)
