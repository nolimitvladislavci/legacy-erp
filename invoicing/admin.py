import os

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    fields = ("description", "quantity", "unit", "unit_price", "discount_percent", "tax_rate", "tax_rate_obj", "inventory_item", "total_price")
    readonly_fields = ("total_price",)
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('doctype_badge', 'number', 'date_issued', 'client_name', 'total_colored', 'status_badge', 'fiscal_badge', 'action_panel')
    list_filter = ('doctype', 'status', 'country', 'is_fiscalized', 'date_issued')
    search_fields = ('number', 'client_name', 'issuer_oib')
    inlines = [InvoiceItemInline]

    def doctype_badge(self, obj):
        colors = {
            'PO': ('#f59e0b', 'Ponuda'),
            'P':  ('#3b82f6', 'Predračun'),
            'R':  ('#16a34a', 'Račun'),
            'A':  ('#8b5cf6', 'Avansni'),
            'S':  ('#ef4444', 'Storno'),
            'GS': ('#64748b', 'Gutschrift'),
        }
        color, label = colors.get(obj.doctype, ('#94a3b8', obj.doctype))
        return format_html(
            '<span style="background:{};color:white;padding:2px 7px;border-radius:3px;'
            'font-size:11px;white-space:nowrap">{}</span>',
            color, label
        )
    doctype_badge.short_description = _('Tip')

    def action_panel(self, obj):
        pdf_url   = reverse('invoicing:generate_pdf',    args=[obj.pk])
        dl_url    = reverse('invoicing:download_pdf',    args=[obj.pk])
        email_url = reverse('invoicing:send_email',      args=[obj.pk])
        xml_url   = reverse('invoicing:generate_eracun', args=[obj.pk])

        btns = []

        # ── Workflow gumbi ovisno o doctype + status ──────────────────────────
        if obj.doctype == 'PO':
            if obj.status == 'DRAFT':
                btns.append(format_html(
                    '<a href="{}" style="background:#64748b;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">✉ Poslano</a>',
                    reverse('invoicing:mark_sent', args=[obj.pk])
                ))
            if obj.status in ('DRAFT', 'SENT'):
                btns.append(format_html(
                    '<a href="{}" style="background:#16a34a;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">✓ Prihvati</a>',
                    reverse('invoicing:mark_accepted', args=[obj.pk])
                ))
                btns.append(format_html(
                    '<a href="{}" style="background:#ef4444;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">✕ Odbij</a>',
                    reverse('invoicing:mark_rejected', args=[obj.pk])
                ))
            if obj.status not in ('REJECTED', 'EXPIRED', 'STORNO'):
                btns.append(format_html(
                    '<a href="{}" style="background:#f59e0b;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">→ Predračun</a>',
                    reverse('invoicing:to_predracun', args=[obj.pk])
                ))
                btns.append(format_html(
                    '<a href="{}" style="background:#0ea5e9;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">→ Račun</a>',
                    reverse('invoicing:to_invoice', args=[obj.pk])
                ))

        elif obj.doctype == 'P':
            if obj.status == 'DRAFT':
                btns.append(format_html(
                    '<a href="{}" style="background:#64748b;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">✉ Poslano</a>',
                    reverse('invoicing:mark_sent', args=[obj.pk])
                ))
            if obj.status not in ('REJECTED', 'EXPIRED', 'STORNO'):
                btns.append(format_html(
                    '<a href="{}" style="background:#0ea5e9;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">→ Kreiraj Račun</a>',
                    reverse('invoicing:to_invoice', args=[obj.pk])
                ))

        elif obj.doctype == 'R':
            if obj.country == 'HR' and not obj.is_fiscalized:
                btns.append(format_html(
                    '<a href="{}" style="background:#16a34a;color:white;padding:4px 10px;'
                    'text-decoration:none;border-radius:3px;font-size:11px">⚡ Fiskaliziraj</a>',
                    reverse('invoicing:fiscalize', args=[obj.pk])
                ))
            elif obj.is_fiscalized:
                btns.append(format_html(
                    '<span style="background:#dcfce7;color:#16a34a;padding:4px 10px;'
                    'border-radius:3px;font-size:11px">✓ Fiskalizirano</span>'
                ))

        # ── Zajednički gumbi ──────────────────────────────────────────────────
        btns.append(format_html(
            '<a href="{}" target="_blank" style="background:#3b82f6;color:white;padding:4px 10px;'
            'text-decoration:none;border-radius:3px;font-size:11px">📄 PDF</a>',
            pdf_url
        ))
        btns.append(format_html(
            '<a href="{}" style="background:#0f172a;color:white;padding:4px 10px;'
            'text-decoration:none;border-radius:3px;font-size:11px">⬇ DL</a>',
            dl_url
        ))
        btns.append(format_html(
            '<a href="{}" style="background:#8b5cf6;color:white;padding:4px 10px;'
            'text-decoration:none;border-radius:3px;font-size:11px">📧 Email</a>',
            email_url
        ))
        btns.append(format_html(
            '<a href="{}" style="background:#f59e0b;color:white;padding:4px 10px;'
            'text-decoration:none;border-radius:3px;font-size:11px">📋 XML</a>',
            xml_url
        ))

        return format_html(
            '<div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">{}</div>',
            ''.join(str(b) for b in btns)
        )
    action_panel.short_description = _('Akcije')

    def total_colored(self, obj):
        color = '#16a34a' if obj.status == 'PAID' else ('#ef4444' if obj.status in ('UNPAID', 'OVERDUE') else '#0f172a')
        return format_html('<strong style="color:{};">{} {}</strong>', color, obj.total, obj.currency)
    total_colored.short_description = _('Iznos')

    def status_badge(self, obj):
        colors = {
            'DRAFT': '#94a3b8', 'SENT': '#3b82f6',
            'ACCEPTED': '#16a34a', 'REJECTED': '#ef4444', 'EXPIRED': '#f59e0b',
            'PAID': '#16a34a', 'UNPAID': '#ef4444', 'OVERDUE': '#dc2626',
            'CANCELLED': '#64748b', 'STORNO': '#1e293b',
        }
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:3px;font-size:11px">{}</span>',
            colors.get(obj.status, '#94a3b8'), obj.get_status_display()
        )
    status_badge.short_description = _('Status')

    def fiscal_badge(self, obj):
        if obj.country != 'HR':
            return format_html('<span style="color:#94a3b8;font-size:11px">–</span>')
        icon, color = ('✓', '#16a34a') if obj.is_fiscalized else ('○', '#f59e0b')
        return format_html(
            '<span style="color:{};font-size:16px" title="JIR: {}">{}</span>',
            color, obj.jir or '', icon
        )
    fiscal_badge.short_description = _('Fisk.')


# ── Fiskalni modeli ───────────────────────────────────────────────────────────
from .fiscal_models import BusinessLocation, FiscalConfig, FiscalOperator, InvoiceProfile, TaxGroup


@admin.register(BusinessLocation)
class BusinessLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_code', 'location_type', 'city', 'is_active')
    list_filter = ('location_type', 'is_active')


@admin.register(FiscalOperator)
class FiscalOperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'oib', 'default_location', 'is_active')
    list_filter = ('is_active',)


@admin.register(TaxGroup)
class TaxGroupAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'rate', 'is_active')



@admin.register(InvoiceProfile)
class InvoiceProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'is_default', 'is_active', 'invoice_prefix', 'next_invoice_number')
    list_filter = ('country', 'is_active', 'is_default')
    search_fields = ('name', 'company_name')
    fieldsets = (
        (_('Profil'), {
            'fields': ('name', 'is_default', 'is_active', 'company'),
        }),
        (_('Podaci izdavatelja'), {
            'fields': ('company_name', 'oib', 'vat_id', 'tax_number', 'address', 'city', 'zip_code', 'country', 'phone', 'email', 'website', 'logo'),
        }),
        (_('Lokalizacija'), {
            'fields': ('language', 'currency', 'default_tax_rate'),
        }),
        (_('Bankovni podaci'), {
            'fields': ('iban', 'swift', 'bank_name'),
        }),
        (_('Numeracija'), {
            'fields': ('invoice_prefix', 'next_invoice_number'),
        }),
        (_('Fiskalizacija'), {
            'fields': ('cert_file', 'cert_path', 'cert_password', 'use_production'),
        }),
        (_('Zadane vrijednosti'), {
            'fields': ('footer_note', 'default_due_days', 'default_payment_method'),
        }),
    )


@admin.register(FiscalConfig)
class FiscalConfigAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'oib', 'cert_status', 'use_production')
    readonly_fields = ('cert_info',)
    fieldsets = (
        (_('Podaci tvrtke'), {
            'fields': ('company_name', 'oib', 'address', 'city', 'email_from', 'default_iban'),
        }),
        (_('Certifikat (.p12)'), {
            'fields': ('cert_file', 'cert_password', 'cert_path', 'cert_info'),
            'description': _(
                'Učitajte novi .p12 certifikat putem polja "Certifikat (.p12)".'
                ' Polje "Putanja certifikata" se automatski ažurira pri učitavanju.'
            ),
        }),
        (_('CIS / Fiskalizacija'), {
            'fields': ('use_production', 'invoice_prefix_hr', 'next_invoice_number'),
        }),
    )

    def cert_status(self, obj):
        path = obj.cert_file.path if obj.cert_file else obj.cert_path
        if not path:
            return format_html('<span style="color:#ef4444">❌ Nije učitan</span>')
        if not os.path.exists(path):
            return format_html('<span style="color:#ef4444">❌ Datoteka nije pronađena</span>')
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import pkcs12
            from django.utils import timezone as tz
            pwd = (obj.cert_password or '').encode() or None
            with open(path, 'rb') as f:
                data = f.read()
            _, cert, _ = pkcs12.load_key_and_certificates(data, pwd, default_backend())
            days = (cert.not_valid_after_utc - tz.now()).days
            color = '#16a34a' if days > 90 else ('#f59e0b' if days > 30 else '#ef4444')
            return format_html('<span style="color:{}"">✓ Validan — istječe za {} dana</span>', color, days)
        except (FileNotFoundError, PermissionError, IOError) as e:
            return format_html('<span style="color:#ef4444">❌ Greška: {}</span>', str(e)[:60])
    cert_status.short_description = _('Certifikat')

    def cert_info(self, obj):
        path = obj.cert_file.path if obj.cert_file else obj.cert_path
        if not path:
            return format_html(
                '<div style="padding:12px;background:#fef2f2;border-left:4px solid #ef4444;border-radius:4px">'
                '<strong>Certifikat nije učitan.</strong><br>'
                'Učitajte .p12 datoteku putem polja iznad ili unesite putanju ručno.'
                '</div>'
            )
        if not os.path.exists(path):
            return format_html(
                '<div style="padding:12px;background:#fef2f2;border-left:4px solid #ef4444;border-radius:4px">'
                '<strong>❌ Datoteka nije pronađena:</strong> {}</div>', path
            )
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import pkcs12
            from django.utils import timezone as tz
            pwd = (obj.cert_password or '').encode() or None
            with open(path, 'rb') as f:
                data = f.read()
            _, cert, _ = pkcs12.load_key_and_certificates(data, pwd, default_backend())
            days = (cert.not_valid_after_utc - tz.now()).days
            color  = '#16a34a' if days > 90 else ('#f59e0b' if days > 30 else '#ef4444')
            bg     = '#f0fdf4' if days > 90 else ('#fffbeb' if days > 30 else '#fef2f2')
            return format_html(
                '<div style="padding:12px;background:{};border-left:4px solid {};border-radius:4px;'
                'font-family:monospace;font-size:13px">'
                '<table style="border-collapse:collapse">'
                '<tr><td style="padding:2px 12px 2px 0;color:#64748b">Subject</td>'
                '    <td><strong>{}</strong></td></tr>'
                '<tr><td style="padding:2px 12px 2px 0;color:#64748b">Izdavač</td>'
                '    <td>{}</td></tr>'
                '<tr><td style="padding:2px 12px 2px 0;color:#64748b">Vrijedi od</td>'
                '    <td>{}</td></tr>'
                '<tr><td style="padding:2px 12px 2px 0;color:#64748b">Istječe</td>'
                '    <td><strong style="color:{};">{} <em>({} dana)</em></strong></td></tr>'
                '<tr><td style="padding:2px 12px 2px 0;color:#64748b">Datoteka</td>'
                '    <td style="color:#94a3b8">{}</td></tr>'
                '</table></div>',
                bg, color,
                cert.subject.rfc4514_string(),
                cert.issuer.rfc4514_string(),
                cert.not_valid_before_utc.strftime('%d.%m.%Y'),
                color,
                cert.not_valid_after_utc.strftime('%d.%m.%Y'), days,
                path,
            )
        except (FileNotFoundError, PermissionError, IOError) as e:
            return format_html(
                '<div style="padding:12px;background:#fef2f2;border-left:4px solid #ef4444;border-radius:4px">'
                '❌ Greška pri čitanju certifikata: {}<br>'
                '<small>Provjerite lozinku ili format .p12 datoteke.</small></div>',
                str(e)
            )
    cert_info.short_description = _('Info o certifikatu')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.cert_file:
            obj.cert_path = obj.cert_file.path
            type(obj).objects.filter(pk=obj.pk).update(cert_path=obj.cert_file.path)
