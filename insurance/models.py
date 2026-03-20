from django.db import models


class InsurancePolicy(models.Model):
    TYPE_CHOICES = [
        ('health', 'Zdravstveno'),
        ('life', 'Zivotno'),
        ('property', 'Imovinska'),
        ('vehicle', 'Vozila'),
        ('liability', 'Odgovornost'),
        ('other', 'Ostalo'),
    ]
    STATUS_CHOICES = [
        ('active', 'Aktivna'),
        ('expired', 'Istekla'),
        ('cancelled', 'Otkazana'),
        ('pending', 'Na cekanju'),
    ]
    policy_number = models.CharField(max_length=100, unique=True, verbose_name='Broj police')
    insurance_type = models.CharField(max_length=20, choices=TYPE_CHOICES,
                                       default='other', verbose_name='Vrsta osiguranja')
    insurer = models.CharField(max_length=200, verbose_name='Osiguravatelj')
    partner = models.ForeignKey('partners.Partner', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='insurance_policies',
                                 verbose_name='Osiguranik')
    start_date = models.DateField(verbose_name='Pocetak')
    end_date = models.DateField(verbose_name='Kraj')
    premium = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Premija')
    coverage_amount = models.DecimalField(max_digits=14, decimal_places=2,
                                           default=0, verbose_name='Iznos pokrica')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                               default='active', verbose_name='Status')
    notes = models.TextField(blank=True, verbose_name='Napomene')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'insurance_policy'
        verbose_name = 'Polica osiguranja'
        verbose_name_plural = 'Police osiguranja'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.policy_number} - {self.insurer} ({self.insurance_type})"
