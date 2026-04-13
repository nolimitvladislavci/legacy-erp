from django.db import models


class AzilPrijava(models.Model):
    naziv = models.CharField(max_length=200, verbose_name="Naziv azila/udruge")
    email = models.EmailField(verbose_name="Email kontakt")
    grad = models.CharField(max_length=100)
    poruka = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    contacted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Prijava azila"
        verbose_name_plural = "Prijave azila"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.naziv} ({self.grad})"
