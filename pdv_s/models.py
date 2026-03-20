"""PDV-S (Prijava PDV-a) — modeli."""
from django.db import models
from django.conf import settings


class PDVSReport(models.Model):
    """Generiran PDV-S obrazac za period."""
    STATUS_CHOICES = [
        ('draft', 'Nacrt'),
        ('final', 'Finalizirano'),
        ('submitted', 'Predano'),
        ('accepted', 'Prihvaceno'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                 related_name='pdvs_reports')
    year = models.IntegerField()
    month = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # I. PRIMLJENE ISPORUKE (input)
    i1_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='I.1 Tuzemne isporuke - osnovica')
    i1_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='I.1 Tuzemne isporuke - pretporez')
    i2_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='I.2 Stjecanje iz EU - osnovica')
    i2_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='I.2 Stjecanje iz EU - pretporez')
    i3_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='I.3 Uvoz - osnovica')
    i3_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='I.3 Uvoz - pretporez')

    # II. OBAVLJENE ISPORUKE (output)
    ii1_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.1 Oporezive 25% - osnovica')
    ii1_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.1 Oporezive 25% - PDV')
    ii2_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.2 Oporezive 13% - osnovica')
    ii2_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.2 Oporezive 13% - PDV')
    ii3_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.3 Oporezive 5% - osnovica')
    ii3_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.3 Oporezive 5% - PDV')
    ii4_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.4 Oslobodene isporuke')
    ii5_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.5 Isporuke u EU')
    ii6_base = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='II.6 Izvoz (trece zemlje)')

    # III. PRETPOREZ (input VAT totals)
    iii_total_pretporez = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iii_ispravak = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='III.4 Ispravak pretporeza')

    # IV. OBVEZA
    iv_pdv_isporuke = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='IV.1 Ukupni PDV na isporuke')
    iv_pretporez = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='IV.2 Ukupni pretporez')
    iv_razlika = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        verbose_name='IV.3 Razlika (+ uplata / - povrat)')

    # Meta
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    xml_file = models.FileField(upload_to='pdv_s/exports/', blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [('company', 'year', 'month')]
        ordering = ['-year', '-month']
        verbose_name = 'PDV-S Obrazac'
        verbose_name_plural = 'PDV-S Obrasci'

    def __str__(self):
        return f'PDV-S {self.month:02d}/{self.year} — {self.company.name}'
