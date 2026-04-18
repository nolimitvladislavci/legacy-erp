"""
FENIX SENTINEL — Living Audit Trail (PLAN_075)
SHA-256 kriptografski lanac za svaku promjenu u sustavu.
"""

import hashlib
import json
from django.contrib.contenttypes.models import ContentType


def record_change(instance, operation: str, user=None, request=None):
    """
    Pozivati iz Django signals ili model.save() override.
    operation: 'create' | 'update' | 'delete'
    """
    from sentinel.models import AuditChain

    # Serijaliziraj podatke
    data = {}
    try:
        for field in instance._meta.fields:
            val = getattr(instance, field.name)
            if hasattr(val, "pk"):
                data[field.name] = str(val.pk)
            elif val is not None:
                data[field.name] = str(val)
            else:
                data[field.name] = None
    except Exception:
        data = {"id": str(getattr(instance, "pk", "unknown"))}

    data_str = json.dumps(data, sort_keys=True)
    data_hash = hashlib.sha256(data_str.encode()).hexdigest()

    # Uzmi prethodni hash
    ct = ContentType.objects.get_for_model(instance)
    last = AuditChain.objects.filter(content_type=ct, object_id=str(instance.pk)).order_by("-created_at").first()

    prev_hash = last.chain_hash if last else "0" * 64
    chain_hash = hashlib.sha256(f"{data_hash}{prev_hash}".encode()).hexdigest()

    # Uzmi company
    company = getattr(instance, "company", None)
    if company is None:
        # Pokušaj kroz related
        for fname in ["terminal", "session", "receipt"]:
            related = getattr(instance, fname, None)
            if related:
                company = getattr(related, "company", None)
                if company:
                    break

    if company is None:
        return  # Bez firme ne snimamo

    ip = None
    if request:
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")

    AuditChain.objects.create(
        company=company,
        content_type=ct,
        object_id=str(instance.pk),
        operation=operation,
        data_hash=data_hash,
        prev_hash=prev_hash,
        chain_hash=chain_hash,
        user_id=user.pk if user else None,
        ip_address=ip,
    )


def verify_chain(company) -> dict:
    """
    Provjeri integritet cijelog lanca za firmu.
    Vraća: {'ok': True, 'count': N} ili {'ok': False, 'broken_at': id, 'count': N}
    """
    from sentinel.models import AuditChain

    entries = AuditChain.objects.filter(company=company).order_by("created_at")

    prev_hashes = {}  # (content_type_id, object_id) -> last chain_hash
    broken = []

    for entry in entries:
        key = (entry.content_type_id, entry.object_id)
        expected_prev = prev_hashes.get(key, "0" * 64)

        if entry.prev_hash != expected_prev:
            broken.append(str(entry.id))
            entry.chain_valid = False
            entry.save(update_fields=["chain_valid"])
        else:
            # Provjeri chain_hash
            expected_chain = hashlib.sha256(f"{entry.data_hash}{entry.prev_hash}".encode()).hexdigest()
            if entry.chain_hash != expected_chain:
                broken.append(str(entry.id))
                entry.chain_valid = False
                entry.save(update_fields=["chain_valid"])

        prev_hashes[key] = entry.chain_hash

    count = entries.count()
    if broken:
        return {"ok": False, "broken_at": broken, "count": count}
    return {"ok": True, "count": count}
