"""
Mandate (Punomoć) — za slanje e-Računa u ime druge firme.

FINA e-Račun zahtijeva da posrednik (opunomoćenik) ima formalni mandat
od vlasnika OIB-a (opunomoćitelja) da šalje e-Račune u njegovo ime.

Workflow:
1. Admin kreira Mandate (principal → agent)
2. Sustav generira PDF punomoći za potpis
3. Potpisan PDF se uploada
4. Admin registrira mandat kod FINA-e
5. Agent koristi svoj certifikat + principal OIB za slanje
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class MandateType(models.TextChoices):
    FULL = "full", _("Potpuna punomoć (slanje + primanje)")
    SEND = "send", _("Samo slanje")
    RECEIVE = "receive", _("Samo primanje")


class MandateStatus(models.TextChoices):
    DRAFT = "draft", _("Nacrt — čeka potpis")
    SIGNED = "signed", _("Potpisan — čeka registraciju kod FINA")
    ACTIVE = "active", _("Aktivan — registriran kod FINA")
    REVOKED = "revoked", _("Opozvan")
    EXPIRED = "expired", _("Istekao")


class Mandate(models.Model):
    """
    Punomoć za slanje e-Računa u ime druge firme.

    principal_company = firma čiji se računi šalju (opunomoćitelj)
    agent_company = firma koja šalje (opunomoćenik, drži certifikat)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    principal_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="mandates_given",
        verbose_name=_("Opunomoćitelj (vlasnik OIB-a)"),
        help_text=_("Firma čiji se e-Računi šalju"),
    )
    principal_oib = models.CharField(
        max_length=11,
        verbose_name=_("OIB opunomoćitelja"),
    )

    agent_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="mandates_held",
        verbose_name=_("Opunomoćenik (posrednik)"),
        help_text=_("Firma koja šalje e-Račune u ime opunomoćitelja"),
    )
    agent_oib = models.CharField(
        max_length=11,
        verbose_name=_("OIB opunomoćenika"),
    )

    mandate_type = models.CharField(
        max_length=10,
        choices=MandateType.choices,
        default=MandateType.FULL,
        verbose_name=_("Tip punomoći"),
    )
    status = models.CharField(
        max_length=10,
        choices=MandateStatus.choices,
        default=MandateStatus.DRAFT,
        verbose_name=_("Status"),
    )

    # FINA registracija
    fina_mandate_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("FINA referenca mandata"),
        help_text=_("ID dobiven od FINA nakon registracije"),
    )
    registered_with_fina = models.BooleanField(
        default=False,
        verbose_name=_("Registrirano kod FINA"),
    )
    fina_registered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Datum registracije kod FINA"),
    )

    # Dokument punomoći
    mandate_document = models.FileField(
        upload_to="einvoice/mandates/",
        null=True,
        blank=True,
        verbose_name=_("PDF punomoći (potpisana)"),
    )

    # Valjanost
    valid_from = models.DateField(verbose_name=_("Vrijedi od"))
    valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Vrijedi do"),
        help_text=_("Prazno = neograničeno"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Aktivan"))

    # Audit
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Kreirao"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, verbose_name=_("Bilješke"))

    class Meta:
        verbose_name = _("Punomoć (e-Račun mandat)")
        verbose_name_plural = _("Punomoći (e-Račun mandati)")
        unique_together = [("principal_company", "agent_company")]
        ordering = ["-created_at"]

    def __str__(self):
        return "%s → %s (%s)" % (self.principal_oib, self.agent_oib, self.get_status_display())

    @property
    def is_valid(self):
        """Provjeri je li mandat trenutno valjan."""
        from django.utils import timezone

        today = timezone.now().date()
        if not self.is_active or self.status != MandateStatus.ACTIVE:
            return False
        if self.valid_from and self.valid_from > today:
            return False
        if self.valid_until and self.valid_until < today:
            return False
        return True

    def revoke(self):
        """Opozovi mandat."""
        self.status = MandateStatus.REVOKED
        self.is_active = False
        self.save(update_fields=["status", "is_active", "updated_at"])
