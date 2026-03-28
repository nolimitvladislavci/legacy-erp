"""
GovExport Models — univerzalni pipeline za državne institucije.

Filozofija: svaki export je "dokument" koji prolazi kroz iste faze
kao fiskalizirani račun — generate → validate → sign → send → confirm.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class GovInstitution(models.Model):
    """Registar državnih institucija kojima šaljemo podatke."""
    code = models.CharField(max_length=20, unique=True, verbose_name=_('Šifra'))
    name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    country = models.CharField(max_length=2, default='HR')
    endpoint_url = models.URLField(blank=True, verbose_name=_('API Endpoint'))
    test_endpoint_url = models.URLField(blank=True, verbose_name=_('Test Endpoint'))
    transport = models.CharField(max_length=20, choices=[
        ('soap', 'SOAP Web Service'),
        ('rest', 'REST API'),
        ('as4', 'AS4 (eDelivery)'),
        ('upload', 'Portal Upload (manual)'),
        ('email', 'Email s potpisom'),
    ], default='upload', verbose_name=_('Transport'))
    auth_type = models.CharField(max_length=20, choices=[
        ('cert', 'mTLS Certifikat'),
        ('bearer', 'Bearer Token'),
        ('basic', 'Basic Auth'),
        ('none', 'Bez autentifikacije'),
    ], default='cert')
    requires_signature = models.BooleanField(default=True, verbose_name=_('Zahtijeva XML potpis'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Državna institucija')
        verbose_name_plural = _('Državne institucije')
        ordering = ['name']

    def __str__(self):
        return f'{self.code}: {self.name}'


class GovDocumentType(models.Model):
    """Tip dokumenta/izvještaja — XSD shema, namespace, perioda."""
    institution = models.ForeignKey(GovInstitution, on_delete=models.CASCADE, related_name='document_types')
    code = models.CharField(max_length=30, verbose_name=_('Šifra dokumenta'))
    name = models.CharField(max_length=200, verbose_name=_('Naziv'))
    xml_namespace = models.CharField(max_length=300, blank=True, verbose_name=_('XML Namespace'))
    xsd_url = models.URLField(blank=True, verbose_name=_('XSD Schema URL'))
    period_type = models.CharField(max_length=20, choices=[
        ('monthly', 'Mjesečno'),
        ('quarterly', 'Kvartalno'),
        ('yearly', 'Godišnje'),
        ('on_demand', 'Na zahtjev'),
        ('realtime', 'Real-time'),
    ], default='monthly')
    deadline_rule = models.CharField(max_length=100, blank=True,
                                      help_text=_('npr. "20. u mjesecu za prethodni" ili "30 dana od kraja kvartala"'))
    generator_class = models.CharField(max_length=100, blank=True,
                                        help_text=_('Python path: gov_export.generators.joppd.JOPPDGenerator'))
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Tip dokumenta')
        verbose_name_plural = _('Tipovi dokumenata')
        unique_together = [('institution', 'code')]

    def __str__(self):
        return f'{self.institution.code}/{self.code}: {self.name}'


class GovExport(models.Model):
    """Jedan export = jedan dokument poslan instituciji. Audit trail."""
    STATUS_CHOICES = [
        ('draft', _('Nacrt — generirano')),
        ('validated', _('Validirano (XSD OK)')),
        ('signed', _('Potpisano (XAdES)')),
        ('sent', _('Poslano')),
        ('accepted', _('Prihvaćeno')),
        ('rejected', _('Odbijeno')),
        ('error', _('Greška')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='gov_exports')
    document_type = models.ForeignKey(GovDocumentType, on_delete=models.CASCADE, related_name='exports')

    # Identifikacija
    reference_number = models.CharField(max_length=50, unique=True, verbose_name=_('Referentni broj'))
    period_start = models.DateField(verbose_name=_('Početak perioda'))
    period_end = models.DateField(verbose_name=_('Kraj perioda'))

    # Status pipeline
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    
    # XML dokument
    xml_content = models.TextField(blank=True, verbose_name=_('XML sadržaj'))
    xml_hash = models.CharField(max_length=64, blank=True, verbose_name=_('SHA-256'))
    xml_size = models.PositiveIntegerField(default=0)

    # Validacija
    is_valid = models.BooleanField(null=True)
    validation_errors = models.JSONField(default=list, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    # Potpis
    is_signed = models.BooleanField(default=False)
    signature_method = models.CharField(max_length=30, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    # Transport
    sent_at = models.DateTimeField(null=True, blank=True)
    transport_method = models.CharField(max_length=30, blank=True)
    transport_response = models.TextField(blank=True)
    confirmation_id = models.CharField(max_length=100, blank=True,
                                        verbose_name=_('ID potvrde (JIR ekvivalent)'))

    # Odgovor institucije
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Državni export')
        verbose_name_plural = _('Državni exporti')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document_type.code} {self.reference_number} [{self.status}]'

    @property
    def institution(self):
        return self.document_type.institution

    @property
    def pipeline_progress(self):
        """0-100% progress kroz pipeline."""
        steps = {'draft': 20, 'validated': 40, 'signed': 60, 'sent': 80, 'accepted': 100}
        return steps.get(self.status, 0)


class GovExportLog(models.Model):
    """Audit log za svaki korak u pipeline-u."""
    export = models.ForeignKey(GovExport, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    step = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=[('ok', 'OK'), ('error', 'Error'), ('skip', 'Skip')])
    message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.export.reference_number} [{self.step}] {self.status}'
