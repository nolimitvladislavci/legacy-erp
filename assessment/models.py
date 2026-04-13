from django.contrib.auth.models import User
from django.db import models

from core.managers import CompanyManager


class FieldAssessment(models.Model):
    ASSESSMENT_TYPES = [
        ("bathroom", "Kupaona"),
        ("optical", "Optika"),
        ("mechanic", "Auto mehaničar"),
        ("other", "Ostalo"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Skica"),
        ("COMPLETED", "Završeno"),
        ("OFFER_SENT", "Ponuda poslana"),
        ("ACCEPTED", "Prihvaćeno"),
        ("REJECTED", "Odbijeno"),
    ]

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="assessments")
    assessment_type = models.CharField(
        max_length=20, choices=ASSESSMENT_TYPES, default="bathroom", verbose_name="Tip procjene"
    )

    # Client info
    client_name = models.CharField(max_length=200, verbose_name="Ime klijenta")
    client_phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    client_email = models.EmailField(blank=True, verbose_name="E-mail")
    client_address = models.CharField(max_length=300, blank=True, verbose_name="Adresa objekta")

    # Staff
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments_created",
        verbose_name="Majstor / inspektor",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT", verbose_name="Status")

    # All form responses as JSON
    json_data = models.JSONField(default=dict, blank=True, verbose_name="Podaci formulara")

    # Expert notes (mirrored from step5 for easy access)
    notes = models.TextField(blank=True, verbose_name="Mišljenje stručnjaka")
    voice_note = models.FileField(
        upload_to="assessments/voice/", null=True, blank=True, verbose_name="Glasovna bilješka"
    )

    # Pricing estimate
    calculated_price_from = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Cijena od (€)"
    )
    calculated_price_to = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Cijena do (€)"
    )

    # Links to other modules
    linked_offer = models.ForeignKey(
        "invoicing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_assessments",
        verbose_name="Ponuda",
    )
    linked_project = models.ForeignKey(
        "burza.ProjectLead",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
        verbose_name="Projekt (Burza)",
    )

    objects = CompanyManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Terenska procjena"
        verbose_name_plural = "Terenske procjene"

    def __str__(self):
        return f"Nalaz #{self.pk} – {self.get_assessment_type_display()} – {self.client_name}"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("assessment:detail", args=[self.pk])

    @property
    def step_data(self):
        data = dict(self.json_data or {})
        for i in range(1, 7):
            data.setdefault(f"step{i}", {})
        return data

    @property
    def completion_percent(self):
        filled = sum(1 for i in range(1, 7) if (self.json_data or {}).get(f"step{i}"))
        return int(filled / 6 * 100)

    @property
    def status_color(self):
        return {
            "DRAFT": "#94a3b8",
            "COMPLETED": "#10b981",
            "OFFER_SENT": "#3b82f6",
            "ACCEPTED": "#c9a84c",
            "REJECTED": "#ef4444",
        }.get(self.status, "#94a3b8")


class AssessmentPhoto(models.Model):
    STEP_CHOICES = [
        (1, "Lokacija"),
        (2, "Instalacije"),
        (3, "Stanje/Dimenzije"),
        (4, "Elementi"),
        (5, "Zaključak"),
        (6, "Stil"),
    ]
    assessment = models.ForeignKey(FieldAssessment, on_delete=models.CASCADE, related_name="photos")
    photo = models.ImageField(upload_to="assessments/photos/%Y/%m/", verbose_name="Fotografija")
    caption = models.CharField(max_length=200, blank=True, verbose_name="Opis")
    step = models.IntegerField(default=3, choices=STEP_CHOICES, verbose_name="Korak")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step", "uploaded_at"]

    def __str__(self):
        return f"Foto #{self.pk} – Nalaz #{self.assessment_id}"
