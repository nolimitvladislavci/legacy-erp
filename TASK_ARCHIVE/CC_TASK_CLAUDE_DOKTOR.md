# CC TASK — CLAUDE DOKTOR
# AI dijagnosticki sustav per-tenant | Prioritet: VISOKI | Rok: 10.04.2026.
# Ivan: "skenira firmu, daje ocjenu, propisuje recept"

## OBVEZNO PRVO: citaj stvarne modele
grep -n "grand_total\|get_grand_total\|total" /var/www/fina-connect/invoicing/models.py | head -20
grep -n "hzmo\|contract_type" /var/www/fina-connect/seasonal/models.py | head -10
grep -n "cert_valid\|valid_until\|certificate" /var/www/fina-connect/fiskalizacija/models.py | head -10
ls /var/www/fina-connect/limit_connect_ai/

## ARHITEKTURA
limit_connect_ai/
  models_doktor.py      <- DiagnosisReport model
  tasks_doktor.py       <- Celery task: run_clinic_diagnostics
  views_doktor.py       <- Dashboard view per-tenant + superadmin
templates/limit_connect_ai/
  doktor_dashboard.html
  doktor_superadmin.html

## KLJUČNE INFORMACIJE (provjereno na serveru)
- Invoice.status choices: DRAFT, SENT, PAID, UNPAID
- Invoice.synesis_id: NULL = novi, NOT NULL = stari synesis uvoz
- Invoice.fiscal_datetime: NULL = nije fiskalizirana
- Invoice.created_at: DateTimeField
- Company.is_vat_registered, Company.pdv_status, Company.email
- SeasonalContract.hzmo_prijava_sent: BooleanField
- FiscalConfig.company: OneToOne s Company (provjeri cert_valid_until field!)
- WhatsApp: core.whatsapp.send_text(phone, message)
- Existing AI models: AIAgentMission, AIReportLog (u limit_connect_ai/models.py)
- ANTHROPIC_API_KEY je u settings

## KORAK 1 -- models_doktor.py

Kreiraj /var/www/fina-connect/limit_connect_ai/models_doktor.py:

from django.db import models

class DiagnosisReport(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
        related_name='diagnosis_reports', verbose_name='Firma')
    report_date = models.DateField(verbose_name='Datum izvjestaja')
    overall_score = models.PositiveSmallIntegerField(default=0, verbose_name='Ukupna ocjena')
    score_delta = models.SmallIntegerField(default=0, verbose_name='Promjena od juce')

    # Kategorije (0-100 svaka)
    score_fiskalizacija = models.PositiveSmallIntegerField(default=100)
    score_pdv = models.PositiveSmallIntegerField(default=100)
    score_cashflow = models.PositiveSmallIntegerField(default=100)
    score_zaposlenici = models.PositiveSmallIntegerField(default=100)
    score_podaci = models.PositiveSmallIntegerField(default=100)
    score_gdpr = models.PositiveSmallIntegerField(default=100)

    ai_summary = models.TextField(blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    # Format: [{"priority": "red"|"yellow"|"green", "title": "...", "detail": "..."}]
    raw_data = models.JSONField(default=dict, blank=True)

    STATUS_CHOICES = [('pending','Na cekanju'), ('done','Gotovo'), ('error','Greska')]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'report_date')]
        ordering = ['-report_date']
        verbose_name = 'Dijagnoza'
        verbose_name_plural = 'Dijagnoze'

    def __str__(self):
        return f"{self.company} | {self.report_date} | {self.overall_score}/100"

    @property
    def status_label(self):
        if self.overall_score >= 80: return ('green', 'Dobro')
        elif self.overall_score >= 60: return ('amber', 'Umjereno')
        else: return ('red', 'Kriticno')

    @property
    def red_recommendations(self):
        return [r for r in self.recommendations if r.get('priority') == 'red']

    @property
    def yellow_recommendations(self):
        return [r for r in self.recommendations if r.get('priority') == 'yellow']

    @property
    def category_scores(self):
        return {
            'Fiskalizacija': self.score_fiskalizacija,
            'PDV': self.score_pdv,
            'Cashflow': self.score_cashflow,
            'Zaposlenici': self.score_zaposlenici,
            'Podaci': self.score_podaci,
            'GDPR': self.score_gdpr,
        }

U limit_connect_ai/models.py dodaj na kraj:
from .models_doktor import DiagnosisReport  # noqa

## KORAK 2 -- tasks_doktor.py

## KORAK 5 -- Celery Beat schedule
U core/celery.py pronadi beat_schedule i dodaj:
    'claude-doktor-nightly': {
        'task': 'limit_connect_ai.tasks_doktor.run_clinic_diagnostics_all',
        'schedule': 10800,
    },
Za nocni run u 3h -- ako imas periodic scheduler import -- koristi hour=3, minute=0.

## KORAK 6 -- grand_total polje (OBAVEZNO)
grep -n "grand_total\|get_grand_total\|def total" /var/www/fina-connect/invoicing/models.py | head -10
Zamijeni raw[overdue_30_amount]=0 s pravom logikom.

## KORAK 7 -- Migration i test
python manage.py makemigrations limit_connect_ai --name=add_diagnosis_report
python manage.py migrate limit_connect_ai
systemctl restart celery-worker gunicorn-fina

## PROVJERA USPJEHA
[ ] migrate OK
[ ] run_clinic_diagnostics_single(id) vraca Firma: X/100
[ ] DiagnosisReport u bazi s ai_summary na hrvatskom
[ ] /doktor/ URL radi
[ ] /superadmin/doktor/ sortirano po score
