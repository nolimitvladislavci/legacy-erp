"""
limit_connect_ai/models_ai_action.py — AIAction model

Svaka automatska AI akcija bilježi se ovdje.
Korisnik vidi što je AI napravio, može revidirati i odobriti.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.managers import CompanyManager


class AIAction(models.Model):
    ACTION_TYPES = [
        ("booking", _("Automatsko knjiženje")),
        ("classification", _("Klasifikacija dokumenta")),
        ("ocr", _("OCR ekstrakcija")),
        ("signal_triage", _("BORG signal trijage")),
        ("recommendation", _("AI preporuka")),
        ("import", _("Smart import")),
        ("compliance", _("Compliance provjera")),
        ("anomaly", _("Anomaly detekcija")),
        ("forecast", _("Prognoza / forecast")),
    ]

    AI_MODELS = [
        ("borg", "BORG AI"),
        ("sonnet", "Claude Sonnet"),
        ("haiku", "Claude Haiku"),
        ("gemini", "Gemini"),
        ("system", "Sustav (auto)"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="ai_actions",
        verbose_name=_("Tvrtka"),
    )
    action_type = models.CharField(
        max_length=30,
        choices=ACTION_TYPES,
        db_index=True,
        verbose_name=_("Tip akcije"),
    )
    description = models.CharField(
        max_length=255, verbose_name=_("Opis"), help_text="Npr. 'Proknjižena faktura #R-2025-142'"
    )
    ai_model = models.CharField(
        max_length=20,
        choices=AI_MODELS,
        default="borg",
        verbose_name=_("AI model"),
    )
    confidence = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Sigurnost (%)"),
        help_text="0–100, None ako nije mjerljivo",
    )
    # Što je uzrokovalo akciju
    source_object = models.CharField(
        max_length=200, blank=True, verbose_name=_("Izvor"), help_text="Npr. 'Invoice #R-2025-142', 'FenixSignal #abc'"
    )
    source_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("URL izvora"),
    )
    # Rezultat akcije
    result_object = models.CharField(
        max_length=200, blank=True, verbose_name=_("Rezultat"), help_text="Npr. 'JournalEntry #456'"
    )
    result_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Detalji rezultata"),
    )
    # Revizija
    is_reviewed = models.BooleanField(
        default=False,
        verbose_name=_("Pregledano"),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lc_reviewed_ai_actions",
        verbose_name=_("Pregledao"),
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, verbose_name=_("Napomena pri pregledu"))

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = CompanyManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("AI akcija")
        verbose_name_plural = _("AI akcije")
        indexes = [
            models.Index(fields=["company", "-created_at"], name="idx_aiaction_company"),
            models.Index(fields=["action_type", "-created_at"], name="idx_aiaction_type"),
            models.Index(fields=["is_reviewed"], name="idx_aiaction_reviewed"),
        ]

    def __str__(self):
        model_label = dict(self.AI_MODELS).get(self.ai_model, self.ai_model)
        return f"[{model_label}] {self.description[:60]}"

    @property
    def confidence_label(self):
        if self.confidence is None:
            return ""
        if self.confidence >= 95:
            return "visoka"
        if self.confidence >= 80:
            return "srednja"
        return "niska"

    @classmethod
    def log(
        cls,
        company,
        action_type,
        description,
        ai_model="borg",
        confidence=None,
        source_object="",
        source_url="",
        result_object="",
        result_data=None,
    ):
        """
        Brzi helper za bilježenje AI akcija iz bilo kojeg dijela sustava.

        Korištenje:
            AIAction.log(
                company=invoice.company,
                action_type="booking",
                description=f"Proknjižena faktura {invoice.number}",
                confidence=98,
                source_object=f"Invoice #{invoice.number}",
                result_object=f"JournalEntry #{je.id}",
            )
        """
        return cls.objects.create(
            company=company,
            action_type=action_type,
            description=description,
            ai_model=ai_model,
            confidence=confidence,
            source_object=source_object,
            source_url=source_url,
            result_object=result_object,
            result_data=result_data or {},
        )
