from django.db import models, DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

class DiagnosisReport(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE,
        related_name="diagnosis_reports", verbose_name="Firma")
    report_date = models.DateField(verbose_name="Datum izvjestaja")
    overall_score = models.PositiveSmallIntegerField(default=0)
    score_delta = models.SmallIntegerField(default=0)
    score_fiskalizacija = models.PositiveSmallIntegerField(default=100)
    score_pdv = models.PositiveSmallIntegerField(default=100)
    score_cashflow = models.PositiveSmallIntegerField(default=100)
    score_zaposlenici = models.PositiveSmallIntegerField(default=100)
    score_podaci = models.PositiveSmallIntegerField(default=100)
    score_gdpr = models.PositiveSmallIntegerField(default=100)
    ai_summary = models.TextField(blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    STATUS_CHOICES = [("pending","Na cekanju"),("done","Gotovo"),("error","Greska")]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("company", "report_date")]
        ordering = ["-report_date"]
        verbose_name = "Dijagnoza"
        verbose_name_plural = "Dijagnoze"

    def __str__(self):
        return f"{self.company} | {self.report_date} | {self.overall_score}/100"

    @property
    def status_label(self):
        if self.overall_score >= 80: return ("green", "Dobro")
        elif self.overall_score >= 60: return ("amber", "Umjereno")
        else: return ("red", "Kriticno")

    @property
    def red_recommendations(self):
        return [r for r in self.recommendations if r.get("priority") == "red"]

    @property
    def yellow_recommendations(self):
        return [r for r in self.recommendations if r.get("priority") == "yellow"]

    @property
    def category_scores(self):
        return {
            "Fiskalizacija": self.score_fiskalizacija,
            "PDV": self.score_pdv,
            "Cashflow": self.score_cashflow,
            "Zaposlenici": self.score_zaposlenici,
            "Podaci": self.score_podaci,
            "GDPR": self.score_gdpr,
        }
