"""
Photo archive signal handlers — auto-registers photos from domain apps into ArhivaEntry.

Pattern: post_save → on_commit → _archive_photo_inner → ArhivaEntry (skip if exists)
Same pattern as invoice/eracun/POS signals in documents/signals.py.

Connected in documents/apps.py ready().
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("documents")


def _archive_photo(instance, image_field_name, source_type, source_app, gps_source=None, tags=None):
    """
    Generic handler for archiving an image into ArhivaEntry.

    Args:
        instance: model instance with the ImageField
        image_field_name: str name of the ImageField on instance
        source_type: ArhivaEntry source_type value
        source_app: app label (e.g. 'stolarija')
        gps_source: callable(instance) → (lat, lng, address) or None
        tags: list of tag strings
    """
    file_field = getattr(instance, image_field_name, None)
    if not file_field or not file_field.name:
        return

    # Resolve company
    company = _resolve_company(instance)
    if not company:
        return

    # Capture values before on_commit (instance may change)
    file_path = file_field.name
    pk = instance.pk
    model_name = instance.__class__.__name__
    user = _resolve_user(instance)
    user_pk = user.pk if user else None
    final_tags = list(tags or [])

    # GPS
    lat, lng, address = None, None, ""
    if gps_source:
        try:
            lat, lng, address = gps_source(instance)
        except Exception:
            pass

    def _inner():
        try:
            from documents.photo_registry import archive_photo
            from django.contrib.auth import get_user_model

            User = get_user_model()
            captured = User.objects.filter(pk=user_pk).first() if user_pk else None

            archive_photo(
                company=company,
                file_path=file_path,
                source_type=source_type,
                source_app=source_app,
                source_model=model_name,
                source_object_id=pk,
                captured_by=captured,
                tags=final_tags,
                latitude=lat,
                longitude=lng,
                address=address or "",
            )
        except Exception:
            logger.exception("signals_photo._inner failed: %s.%s.%s", source_app, model_name, image_field_name)

    transaction.on_commit(_inner)


def _resolve_company(obj):
    """Walk FK chain to find company."""
    if hasattr(obj, "company_id") and obj.company_id:
        return obj.company
    if hasattr(obj, "session") and hasattr(obj.session, "company"):
        return obj.session.company
    if hasattr(obj, "installation") and hasattr(obj.installation, "company"):
        return obj.installation.company
    if hasattr(obj, "production_order") and hasattr(obj.production_order, "company"):
        return obj.production_order.company
    if hasattr(obj, "warranty") and hasattr(obj.warranty, "session"):
        return obj.warranty.session.company
    if hasattr(obj, "project") and hasattr(obj.project, "company"):
        return obj.project.company
    return None


def _resolve_user(obj):
    """Walk FK chain to find user."""
    for attr in ("captured_by", "created_by", "team_lead", "technician", "user", "archived_by"):
        user = getattr(obj, attr, None)
        if user and hasattr(user, "pk"):
            return user
    return None


# ═══════════════════════════════════════════════════════════════
# GPS SOURCE RESOLVERS
# ═══════════════════════════════════════════════════════════════


def _gps_from_session(instance):
    """Stolarija: GPS from MeasurementSession."""
    session = None
    if hasattr(instance, "session"):
        session = instance.session
    elif hasattr(instance, "installation") and hasattr(instance.installation, "production_order"):
        session = instance.installation.production_order.offer.session
    elif hasattr(instance, "production_order"):
        session = instance.production_order.offer.session

    if session:
        return (
            getattr(session, "latitude", None),
            getattr(session, "longitude", None),
            getattr(session, "address", "") or "",
        )
    return (None, None, "")


def _gps_from_self(instance):
    """Model has lat/lng directly."""
    return (
        getattr(instance, "latitude", None),
        getattr(instance, "longitude", None),
        getattr(instance, "address", "") or "",
    )


# ═══════════════════════════════════════════════════════════════
# SIGNAL CONNECTIONS
# ═══════════════════════════════════════════════════════════════


def connect_photo_signals():
    """Connect all photo archive signals. Called from documents.apps.ready()."""

    # ─── STOLARIJA ─────────────────────────────────────────────
    try:
        from stolarija.models import (
            InstallationChecklist,
            InstallationOrder,
            Measurement,
            ServiceMessage,
            ServiceVisit,
            WindowWarranty,
        )

        @receiver(post_save, sender=Measurement)
        def _stol_measurement(sender, instance, **kw):
            _archive_photo(
                instance,
                "photo_before",
                "before_photo",
                "stolarija",
                gps_source=_gps_from_session,
                tags=["mjerenje", "teren"],
            )

        @receiver(post_save, sender=InstallationOrder)
        def _stol_install(sender, instance, **kw):
            _archive_photo(
                instance,
                "photo_before",
                "before_photo",
                "stolarija",
                gps_source=_gps_from_session,
                tags=["ugradnja", "prije"],
            )
            _archive_photo(
                instance,
                "photo_after",
                "after_photo",
                "stolarija",
                gps_source=_gps_from_session,
                tags=["ugradnja", "poslije"],
            )

        @receiver(post_save, sender=InstallationChecklist)
        def _stol_checklist(sender, instance, **kw):
            _archive_photo(
                instance,
                "photo_result",
                "after_photo",
                "stolarija",
                gps_source=_gps_from_session,
                tags=["ugradnja", "rezultat"],
            )

        @receiver(post_save, sender=WindowWarranty)
        def _stol_warranty(sender, instance, **kw):
            _archive_photo(
                instance,
                "handover_photo",
                "site_photo",
                "stolarija",
                gps_source=_gps_from_session,
                tags=["primopredaja"],
            )

        @receiver(post_save, sender=ServiceVisit)
        def _stol_service(sender, instance, **kw):
            _archive_photo(instance, "photo", "site_photo", "stolarija", tags=["servis", "pregled"])

        @receiver(post_save, sender=ServiceMessage)
        def _stol_message(sender, instance, **kw):
            _archive_photo(instance, "attachment", "complaint_photo", "stolarija", tags=["poruka", "prilog"])

        logger.info("signals_photo: stolarija connected (6 models)")
    except ImportError:
        pass

    # ─── DELIVERY ──────────────────────────────────────────────
    try:
        from delivery.models import ConsolidatedDelivery, DeliveryStop

        @receiver(post_save, sender=DeliveryStop)
        def _del_stop(sender, instance, **kw):
            _archive_photo(
                instance,
                "delivery_photo",
                "delivery_proof",
                "delivery",
                gps_source=_gps_from_self,
                tags=["dostava", "dokaz"],
            )

        @receiver(post_save, sender=ConsolidatedDelivery)
        def _del_consolidated(sender, instance, **kw):
            _archive_photo(instance, "delivery_photo", "delivery_proof", "delivery", tags=["dostava", "konsolidirano"])
            _archive_photo(instance, "recipient_signature", "delivery_proof", "delivery", tags=["dostava", "potpis"])

        logger.info("signals_photo: delivery connected")
    except ImportError:
        pass

    # ─── WORKTIME ──────────────────────────────────────────────
    try:
        from worktime.models import ProjectPhoto

        @receiver(post_save, sender=ProjectPhoto)
        def _wt_project(sender, instance, **kw):
            _archive_photo(instance, "image", "site_photo", "worktime", tags=["gradiliste", "projekt"])

        logger.info("signals_photo: worktime connected")
    except ImportError:
        pass

    # ─── PRODUCTION ────────────────────────────────────────────
    try:
        from production.models import QualityCheck

        @receiver(post_save, sender=QualityCheck)
        def _prod_qc(sender, instance, **kw):
            _archive_photo(instance, "photo", "qc_photo", "production", tags=["kvaliteta", "kontrola"])

        logger.info("signals_photo: production connected")
    except ImportError:
        pass

    # ─── ASSESSMENT ────────────────────────────────────────────
    try:
        from assessment.models import AssessmentPhoto

        @receiver(post_save, sender=AssessmentPhoto)
        def _assess_photo(sender, instance, **kw):
            _archive_photo(instance, "photo", "site_photo", "assessment", tags=["inspekcija", "procjena"])

        logger.info("signals_photo: assessment connected")
    except ImportError:
        pass

    # ─── LIVESTOCK ─────────────────────────────────────────────
    try:
        from livestock.models import HealthRecord, Pet

        @receiver(post_save, sender=Pet)
        def _pet_photo(sender, instance, **kw):
            _archive_photo(instance, "photo", "animal_photo", "livestock", tags=["zivotinja"])

        @receiver(post_save, sender=HealthRecord)
        def _health_photo(sender, instance, **kw):
            _archive_photo(instance, "photo", "animal_photo", "livestock", tags=["zdravlje", "pregled"])

        logger.info("signals_photo: livestock connected")
    except ImportError:
        pass

    # ─── INVOICING ─────────────────────────────────────────────
    try:
        from invoicing.models import Invoice

        @receiver(post_save, sender=Invoice)
        def _inv_photo(sender, instance, **kw):
            _archive_photo(instance, "photo", "receipt_scan", "invoicing", tags=["racun", "fotografija"])

        logger.info("signals_photo: invoicing connected")
    except ImportError:
        pass

    logger.info("signals_photo: all connections complete")
