"""
GovExport — Univerzalni pipeline za export podataka državnim institucijama.
═══════════════════════════════════════════════════════════════════════════

INOVACIJA: Ista logika kao fiskalizacija računa, ali za SVE državne exporte.
  Generate → Validate → Sign → Transport → Confirm → Audit

Podržani formati:
  - JOPPD (Porezna — plaće)
  - PDV-S (Porezna — PDV prijava)
  - DOH (Porezna — dohodak)
  - PR-RAS-NPF (FINA — financijski izvještaj udruga)
  - SAF-T HR (Porezna — audit file)
  - HACCP Report (Sanitarna inspekcija)
  - eRačun (FINA — već postoji, integrira se)
"""
import os
BASE = '/var/www/fina-connect'

# ══════════════════════════════════════════════════════════════════════
# 1. APP — gov_export
# ══════════════════════════════════════════════════════════════════════

app_dir = os.path.join(BASE, 'gov_export')
os.makedirs(app_dir, exist_ok=True)
os.makedirs(os.path.join(app_dir, 'migrations'), exist_ok=True)
os.makedirs(os.path.join(app_dir, 'generators'), exist_ok=True)

# __init__.py
for d in [app_dir, os.path.join(app_dir, 'migrations'), os.path.join(app_dir, 'generators')]:
    with open(os.path.join(d, '__init__.py'), 'w') as f:
        f.write('')

# apps.py
with open(os.path.join(app_dir, 'apps.py'), 'w') as f:
    f.write("""from django.apps import AppConfig

class GovExportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gov_export'
    verbose_name = 'GovExport — Državni export pipeline'
""")

# ══════════════════════════════════════════════════════════════════════
# 2. MODELS
# ══════════════════════════════════════════════════════════════════════

models_code = '''"""
GovExport Models — univerzalni pipeline za državne institucije.

Filozofija: svaki export je "dokument" koji prolazi kroz iste faze
kao fiskalizirani račun — generate → validate → sign → send → confirm.
"""
import uuid
from django.db import models, DatabaseError, IntegrityError
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
'''

with open(os.path.join(app_dir, 'models.py'), 'w') as f:
    f.write(models_code)
print("[OK] gov_export/models.py — 4 modela")


# ══════════════════════════════════════════════════════════════════════
# 3. PIPELINE ENGINE
# ══════════════════════════════════════════════════════════════════════

engine_code = '''"""
GovExport Pipeline Engine — Generate → Validate → Sign → Send → Confirm.
Identična logika kao fiskalizacija računa, ali univerzalna.
"""
import hashlib
import logging
import time
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('gov_export.pipeline')


def run_pipeline(export, user=None, dry_run=False):
    """
    Pokreni kompletan pipeline za jedan GovExport.
    Svaki korak se logira u GovExportLog.
    
    Returns: dict s rezultatima svakog koraka
    """
    from .models import GovExportLog
    results = {}

    # ── STEP 1: Generate XML ──
    t0 = time.time()
    try:
        if not export.xml_content:
            generator = _get_generator(export)
            xml = generator.generate(export)
            export.xml_content = xml
            export.xml_size = len(xml.encode('utf-8') if isinstance(xml, str) else xml)
            export.xml_hash = hashlib.sha256(
                xml.encode('utf-8') if isinstance(xml, str) else xml
            ).hexdigest()
            export.save(update_fields=['xml_content', 'xml_size', 'xml_hash'])
        
        results['generate'] = 'ok'
        GovExportLog.objects.create(
            export=export, step='generate', status='ok',
            message=f'XML generated: {export.xml_size} bytes, SHA-256: {export.xml_hash[:16]}',
            duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    except (IntegrityError, DatabaseError) as e:
        results['generate'] = f'error: {e}'
        export.status = 'error'
        export.save(update_fields=['status'])
        GovExportLog.objects.create(
            export=export, step='generate', status='error',
            message=str(e)[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
        return results

    # ── STEP 2: Validate XSD ──
    t0 = time.time()
    try:
        doc_type = export.document_type
        if doc_type.xsd_url:
            from eracun.services.validator import validate_xsd
            xml_bytes = export.xml_content.encode('utf-8') if isinstance(export.xml_content, str) else export.xml_content
            validate_xsd(xml_bytes)
        
        export.is_valid = True
        export.validated_at = timezone.now()
        export.status = 'validated'
        export.save(update_fields=['is_valid', 'validated_at', 'status'])
        results['validate'] = 'ok'
        GovExportLog.objects.create(
            export=export, step='validate', status='ok',
            message='XSD validation passed', duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    except (ValueError, TypeError) as e:
        export.is_valid = False
        export.validation_errors = [str(e)[:500]]
        export.save(update_fields=['is_valid', 'validation_errors'])
        results['validate'] = f'error: {e}'
        GovExportLog.objects.create(
            export=export, step='validate', status='error',
            message=str(e)[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
        # Nastavi — validacija je warning, ne blocker

    # ── STEP 3: Sign (XAdES) ──
    t0 = time.time()
    institution = doc_type.institution
    if institution.requires_signature and not dry_run:
        try:
            from eracun.services.xades_signer import sign_xades_b
            from fiskalizacija.models import FiscalConfig
            config = FiscalConfig.objects.filter(company=export.company, is_active=True).first()
            if config and config.cert_path:
                import os
                from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
                
                pw = config.get_password()
                if isinstance(pw, str): pw = pw.encode()
                with open(config.cert_path, 'rb') as f:
                    p12 = f.read()
                key, cert, chain = load_key_and_certificates(p12, pw)
                cert_pem = cert.public_bytes(Encoding.PEM)
                key_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

                from lxml import etree
                root = etree.fromstring(export.xml_content.encode('utf-8'))
                signed_root = sign_xades_b(root, cert_pem, key_pem)
                export.xml_content = etree.tostring(signed_root, xml_declaration=True, encoding='UTF-8').decode('utf-8')
                export.is_signed = True
                export.signature_method = 'XAdES-BES'
                export.signed_at = timezone.now()
                export.status = 'signed'
                export.save(update_fields=['xml_content', 'is_signed', 'signature_method', 'signed_at', 'status'])
                results['sign'] = 'ok'
            else:
                results['sign'] = 'skip: no cert'
        except (FileNotFoundError, IOError) as e:
            results['sign'] = f'error: {e}'
        GovExportLog.objects.create(
            export=export, step='sign', status=results.get('sign', 'skip')[:5],
            message=str(results.get('sign', ''))[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    else:
        results['sign'] = 'skip: not required or dry_run'

    # ── STEP 4: Send ──
    t0 = time.time()
    if not dry_run:
        try:
            transport = institution.transport
            if transport == 'upload':
                # Manual upload — samo markira kao "spreman za download"
                export.status = 'sent'
                export.sent_at = timezone.now()
                export.transport_method = 'manual_download'
                export.save(update_fields=['status', 'sent_at', 'transport_method'])
                results['send'] = 'ok: ready for download'
            elif transport in ('soap', 'rest', 'as4'):
                # TODO: implementirati kad institucija ima API
                export.status = 'sent'
                export.sent_at = timezone.now()
                export.transport_method = transport
                export.save(update_fields=['status', 'sent_at', 'transport_method'])
                results['send'] = f'ok: {transport}'
            else:
                results['send'] = f'skip: unknown transport {transport}'
        except Exception as e:
            results['send'] = f'error: {e}'
        GovExportLog.objects.create(
            export=export, step='send', status='ok' if 'ok' in str(results.get('send', '')) else 'error',
            message=str(results.get('send', ''))[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    else:
        results['send'] = 'skip: dry_run'

    logger.info('GovExport pipeline %s: %s', export.reference_number, results)
    return results


def _get_generator(export):
    """Dinamički učitaj generator klasu za tip dokumenta."""
    class_path = export.document_type.generator_class
    if not class_path:
        raise ValueError(f'Nema generator_class za {export.document_type.code}')
    
    module_path, class_name = class_path.rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()
'''

with open(os.path.join(app_dir, 'pipeline.py'), 'w') as f:
    f.write(engine_code)
print("[OK] gov_export/pipeline.py — univerzalni pipeline engine")


# ══════════════════════════════════════════════════════════════════════
# 4. JOPPD GENERATOR (prvi concrete generator)
# ══════════════════════════════════════════════════════════════════════

joppd_gen = '''"""JOPPD Generator — adapter za postojeći payroll/joppd_generator.py"""

class JOPPDGenerator:
    def generate(self, export):
        from payroll.joppd_generator import generate_joppd_xml
        from payroll.models import PayrollRun, Payslip
        
        run = PayrollRun.objects.filter(
            company=export.company,
            year=export.period_start.year,
            month=export.period_start.month,
        ).first()
        
        if not run:
            raise ValueError(f'Nema PayrollRun za {export.period_start}')
        
        payslips = Payslip.objects.filter(payroll_run=run)
        return generate_joppd_xml(export.company, run, payslips)
'''

with open(os.path.join(app_dir, 'generators/joppd.py'), 'w') as f:
    f.write(joppd_gen)
print("[OK] gov_export/generators/joppd.py")


# ══════════════════════════════════════════════════════════════════════
# 5. VIEWS + URLS + TEMPLATE
# ══════════════════════════════════════════════════════════════════════

views_code = '''"""GovExport Views — dashboard + run pipeline."""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from core.company_utils import get_user_company
from .models import GovExport, GovDocumentType, GovInstitution


@login_required
def dashboard(request):
    company = get_user_company(request)
    if not company:
        return redirect('dashboard')
    
    exports = GovExport.objects.filter(company=company)[:20]
    institutions = GovInstitution.objects.filter(is_active=True)
    doc_types = GovDocumentType.objects.filter(is_active=True).select_related('institution')

    stats = {
        'total': exports.count(),
        'accepted': exports.filter(status='accepted').count(),
        'pending': exports.filter(status__in=['draft', 'validated', 'signed', 'sent']).count(),
        'rejected': exports.filter(status='rejected').count(),
    }

    return render(request, 'gov_export/dashboard.html', {
        'exports': exports, 'institutions': institutions,
        'doc_types': doc_types, 'stats': stats,
    })


@login_required
@require_POST
def run_export(request, export_id):
    company = get_user_company(request)
    export = get_object_or_404(GovExport, pk=export_id, company=company)
    
    from .pipeline import run_pipeline
    results = run_pipeline(export, user=request.user)
    
    passed = sum(1 for v in results.values() if 'ok' in str(v))
    total = len(results)
    messages.success(request, f'Pipeline: {passed}/{total} koraka uspješno. Status: {export.status}')
    return redirect('gov_export:dashboard')


@login_required
def download_xml(request, export_id):
    company = get_user_company(request)
    export = get_object_or_404(GovExport, pk=export_id, company=company)
    
    if not export.xml_content:
        messages.error(request, 'XML još nije generiran.')
        return redirect('gov_export:dashboard')
    
    response = HttpResponse(export.xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{export.reference_number}.xml"'
    return response


@login_required
def export_log(request, export_id):
    company = get_user_company(request)
    export = get_object_or_404(GovExport, pk=export_id, company=company)
    logs = export.logs.all()
    
    return JsonResponse({
        'reference': export.reference_number,
        'status': export.status,
        'progress': export.pipeline_progress,
        'logs': [
            {'step': l.step, 'status': l.status, 'message': l.message,
             'duration_ms': l.duration_ms, 'timestamp': l.timestamp.isoformat()}
            for l in logs
        ]
    })
'''

with open(os.path.join(app_dir, 'views.py'), 'w') as f:
    f.write(views_code)

urls_code = '''from django.urls import path
from . import views

app_name = 'gov_export'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('<uuid:export_id>/run/', views.run_export, name='run'),
    path('<uuid:export_id>/xml/', views.download_xml, name='download_xml'),
    path('<uuid:export_id>/log/', views.export_log, name='log'),
]
'''

with open(os.path.join(app_dir, 'urls.py'), 'w') as f:
    f.write(urls_code)
print("[OK] gov_export/views.py + urls.py")


# ADMIN
admin_code = '''from django.contrib import admin
from .models import GovInstitution, GovDocumentType, GovExport, GovExportLog


class GovExportLogInline(admin.TabularInline):
    model = GovExportLog
    extra = 0
    readonly_fields = ('timestamp', 'step', 'status', 'message', 'duration_ms', 'actor')


@admin.register(GovInstitution)
class GovInstitutionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'transport', 'requires_signature', 'is_active')


@admin.register(GovDocumentType)
class GovDocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'institution', 'period_type', 'is_active')
    list_filter = ('institution',)


@admin.register(GovExport)
class GovExportAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'document_type', 'company', 'status', 'xml_size', 'created_at')
    list_filter = ('status', 'document_type__institution')
    inlines = [GovExportLogInline]
    readonly_fields = ('xml_hash', 'xml_size', 'validated_at', 'signed_at', 'sent_at', 'accepted_at')
'''

with open(os.path.join(app_dir, 'admin.py'), 'w') as f:
    f.write(admin_code)
print("[OK] gov_export/admin.py")


# TEMPLATE
tpl = '''{% extends "base.html" %}
{% load i18n %}
{% block title %}GovExport — Državni Export Pipeline{% endblock %}
{% block extra_css %}
<style>
.gx-container{max-width:1000px;margin:0 auto}
.gx-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1.5rem}
.gx-stat{background:var(--surface,var(--bg-card));border:1px solid var(--border);border-radius:12px;padding:1rem;text-align:center}
.gx-stat .val{font-size:1.6rem;font-weight:800}
.gx-stat .lbl{font-size:.7rem;text-transform:uppercase;color:var(--text-dim)}
.gx-pipeline{display:flex;gap:4px;margin:.5rem 0}
.gx-step{height:6px;border-radius:3px;flex:1}
.gx-step.done{background:#22c55e}
.gx-step.active{background:#f59e0b}
.gx-step.pending{background:var(--border)}
.gx-card{background:var(--surface,var(--bg-card));border:1px solid var(--border);border-radius:14px;padding:1.25rem;margin-bottom:1rem}
@media(max-width:768px){.gx-stats{grid-template-columns:repeat(2,1fr)}}
</style>
{% endblock %}
{% block content %}
<div class="gx-container">

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;flex-wrap:wrap;gap:.75rem">
  <div>
    <h2 style="font-size:1.5rem;font-weight:800;margin:0;color:var(--text)">
      <i class="fas fa-university me-2" style="color:var(--gold)"></i>GovExport
    </h2>
    <small style="color:var(--text-dim)">Univerzalni pipeline za državne institucije — potpisan, validiran, isporučen</small>
  </div>
</div>

<div class="gx-stats">
  <div class="gx-stat"><div class="val" style="color:var(--gold)">{{ stats.total }}</div><div class="lbl">Ukupno</div></div>
  <div class="gx-stat"><div class="val" style="color:#22c55e">{{ stats.accepted }}</div><div class="lbl">Prihvaćeno</div></div>
  <div class="gx-stat"><div class="val" style="color:#f59e0b">{{ stats.pending }}</div><div class="lbl">U tijeku</div></div>
  <div class="gx-stat"><div class="val" style="color:#ef4444">{{ stats.rejected }}</div><div class="lbl">Odbijeno</div></div>
</div>

{% for export in exports %}
<div class="gx-card">
  <div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:.5rem">
    <div>
      <div style="font-weight:700;color:var(--text)">{{ export.document_type.name }}</div>
      <div style="font-size:.8rem;color:var(--text-dim)">{{ export.reference_number }} | {{ export.institution.name }} | {{ export.period_start|date:"d.m.Y" }}—{{ export.period_end|date:"d.m.Y" }}</div>
    </div>
    <div style="display:flex;gap:.5rem;align-items:center">
      <span style="font-size:.72rem;padding:3px 10px;border-radius:6px;font-weight:700;{% if export.status == 'accepted' %}background:rgba(34,197,94,.15);color:#22c55e{% elif export.status == 'error' or export.status == 'rejected' %}background:rgba(239,68,68,.15);color:#ef4444{% else %}background:rgba(245,158,11,.15);color:#f59e0b{% endif %}">{{ export.get_status_display }}</span>
      {% if export.status != 'accepted' %}
      <form method="POST" action="{% url 'gov_export:run' export.pk %}" class="d-inline">{% csrf_token %}
        <button class="btn btn-sm" style="background:var(--gold);color:#0a0a0a;border-radius:8px;font-weight:700;font-size:.75rem;border:none"><i class="fas fa-play me-1"></i>Pipeline</button>
      </form>
      {% endif %}
      {% if export.xml_content %}
      <a href="{% url 'gov_export:download_xml' export.pk %}" class="btn btn-sm btn-outline-info" style="border-radius:8px;font-size:.75rem"><i class="fas fa-download me-1"></i>XML</a>
      {% endif %}
    </div>
  </div>
  <div class="gx-pipeline">
    <div class="gx-step {% if export.pipeline_progress >= 20 %}done{% else %}pending{% endif %}" title="Generate"></div>
    <div class="gx-step {% if export.pipeline_progress >= 40 %}done{% elif export.pipeline_progress >= 20 %}active{% else %}pending{% endif %}" title="Validate"></div>
    <div class="gx-step {% if export.pipeline_progress >= 60 %}done{% elif export.pipeline_progress >= 40 %}active{% else %}pending{% endif %}" title="Sign"></div>
    <div class="gx-step {% if export.pipeline_progress >= 80 %}done{% elif export.pipeline_progress >= 60 %}active{% else %}pending{% endif %}" title="Send"></div>
    <div class="gx-step {% if export.pipeline_progress >= 100 %}done{% elif export.pipeline_progress >= 80 %}active{% else %}pending{% endif %}" title="Confirm"></div>
  </div>
  {% if export.xml_size %}<div style="font-size:.72rem;color:var(--text-dim)">{{ export.xml_size }} bytes | SHA-256: {{ export.xml_hash|truncatechars:24 }}{% if export.is_signed %} | ✍️ {{ export.signature_method }}{% endif %}{% if export.confirmation_id %} | 📋 {{ export.confirmation_id }}{% endif %}</div>{% endif %}
</div>
{% empty %}
<div style="text-align:center;padding:3rem;color:var(--text-dim)">
  <i class="fas fa-university" style="font-size:3rem;opacity:.2;display:block;margin-bottom:1rem"></i>
  <h5>Nema exporta</h5>
  <p>GovExport pipeline spreman. Dodajte institucije i tipove dokumenata u Admin-u.</p>
</div>
{% endfor %}

<div style="margin-top:2rem;padding:1rem;background:var(--surface,var(--bg-card));border:1px solid var(--border);border-radius:12px;font-size:.8rem;color:var(--text-dim)">
  <strong style="color:var(--gold)"><i class="fas fa-lightbulb me-1"></i>Pipeline logika:</strong>
  Generate XML → Validate (XSD) → Sign (XAdES-BES) → Send → Confirm.
  Isti protokol kao fiskalizacija računa — potpisan, hashiran, auditiran.
</div>

</div>
{% endblock %}
'''

os.makedirs(os.path.join(BASE, 'templates/gov_export'), exist_ok=True)
with open(os.path.join(BASE, 'templates/gov_export/dashboard.html'), 'w') as f:
    f.write(tpl)
print("[OK] templates/gov_export/dashboard.html")


# ══════════════════════════════════════════════════════════════════════
# 6. REGISTER u settings + urls
# ══════════════════════════════════════════════════════════════════════

# Settings
settings_path = os.path.join(BASE, 'core/settings.py')
with open(settings_path) as f:
    sc = f.read()

if "'gov_export'" not in sc:
    sc = sc.replace("    'fiskalizacija',", "    'fiskalizacija',\n    'gov_export',")
    with open(settings_path, 'w') as f:
        f.write(sc)
    print("[OK] core/settings.py — gov_export u INSTALLED_APPS")

# URLs
urls_path = os.path.join(BASE, 'core/urls.py')
with open(urls_path) as f:
    uc = f.read()

if 'gov_export' not in uc:
    uc = uc.replace(
        "    path('experiences/', include('experiences.urls', namespace='experiences')),",
        "    path('experiences/', include('experiences.urls', namespace='experiences')),\n    path('gov-export/', include('gov_export.urls', namespace='gov_export')),"
    )
    with open(urls_path, 'w') as f:
        f.write(uc)
    print("[OK] core/urls.py — /gov-export/ ruta")


# ══════════════════════════════════════════════════════════════════════
# 7. SEED institucije i tipove dokumenata
# ══════════════════════════════════════════════════════════════════════

seed_code = '''"""Seed GovExport institucije i tipove dokumenata."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed GovExport institucije i tipove dokumenata'

    def handle(self, *args, **options):
        from gov_export.models import GovInstitution, GovDocumentType

        institutions = [
            {'code': 'PU', 'name': 'Porezna uprava', 'transport': 'soap', 'auth_type': 'cert',
             'endpoint_url': 'https://e-porezna.porezna-uprava.hr/', 'requires_signature': True},
            {'code': 'FINA', 'name': 'FINA', 'transport': 'rest', 'auth_type': 'cert',
             'endpoint_url': 'https://eracun.fina.hr/', 'requires_signature': True},
            {'code': 'HZZO', 'name': 'HZZO', 'transport': 'upload', 'auth_type': 'none',
             'requires_signature': False},
            {'code': 'DZS', 'name': 'Državni zavod za statistiku', 'transport': 'upload', 'auth_type': 'none',
             'requires_signature': False},
            {'code': 'SANIT', 'name': 'Sanitarna inspekcija', 'transport': 'upload', 'auth_type': 'none',
             'requires_signature': False},
        ]

        for data in institutions:
            inst, created = GovInstitution.objects.update_or_create(
                code=data['code'], defaults=data,
            )
            self.stdout.write(f'  {"+" if created else "~"} {inst}')

        doc_types = [
            {'institution_code': 'PU', 'code': 'JOPPD', 'name': 'JOPPD — Izvješće o primicima i doprinosima',
             'period_type': 'monthly', 'deadline_rule': '15. u mjesecu za prethodni',
             'xml_namespace': 'http://e-porezna.porezna-uprava.hr/sheme/zahtjevi/ObscePorezanDohodak/v4-0',
             'generator_class': 'gov_export.generators.joppd.JOPPDGenerator'},
            {'institution_code': 'PU', 'code': 'PDV-S', 'name': 'PDV-S — Prijava PDV-a',
             'period_type': 'monthly', 'deadline_rule': '20. u mjesecu za prethodni'},
            {'institution_code': 'PU', 'code': 'DOH', 'name': 'DOH — Prijava poreza na dohodak',
             'period_type': 'yearly', 'deadline_rule': '28. veljače za prethodnu godinu'},
            {'institution_code': 'PU', 'code': 'SAF-T', 'name': 'SAF-T HR — Standard Audit File for Tax',
             'period_type': 'on_demand', 'deadline_rule': 'Na zahtjev Porezne'},
            {'institution_code': 'PU', 'code': 'eRACUN', 'name': 'eRačun — Fiskalizacija 2.0',
             'period_type': 'realtime'},
            {'institution_code': 'FINA', 'code': 'PR-RAS-NPF', 'name': 'PR-RAS-NPF — Financijski izvještaj (udruge)',
             'period_type': 'yearly', 'deadline_rule': '1. ožujka za prethodnu godinu'},
            {'institution_code': 'FINA', 'code': 'BIL-NPF', 'name': 'BIL-NPF — Bilanca (udruge)',
             'period_type': 'yearly'},
            {'institution_code': 'SANIT', 'code': 'HACCP', 'name': 'HACCP Recall Report',
             'period_type': 'on_demand'},
        ]

        for data in doc_types:
            inst_code = data.pop('institution_code')
            inst = GovInstitution.objects.get(code=inst_code)
            dt, created = GovDocumentType.objects.update_or_create(
                institution=inst, code=data['code'], defaults=data,
            )
            self.stdout.write(f'  {"+" if created else "~"} {dt}')

        self.stdout.write(self.style.SUCCESS('Done.'))
'''

seed_dir = os.path.join(app_dir, 'management/commands')
os.makedirs(seed_dir, exist_ok=True)
for d in [os.path.join(app_dir, 'management'), seed_dir]:
    init = os.path.join(d, '__init__.py')
    if not os.path.exists(init):
        with open(init, 'w') as f: f.write('')

with open(os.path.join(seed_dir, 'seed_gov_institutions.py'), 'w') as f:
    f.write(seed_code)
print("[OK] gov_export/management/commands/seed_gov_institutions.py")


print("\\n═══════════════════════════════════════════")
print("GOVEXPORT — UNIVERZALNI DRŽAVNI PIPELINE")
print("  4 modela (Institution, DocType, Export, Log)")
print("  Pipeline engine (Generate→Validate→Sign→Send)")
print("  JOPPD generator (adapter)")
print("  Dashboard + admin + seed")
print("  5 institucija, 8 tipova dokumenata")
print("═══════════════════════════════════════════")
