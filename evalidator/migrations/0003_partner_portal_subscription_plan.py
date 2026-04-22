"""
Ručno pisana migracija 0003_partner_portal_subscription_plan
- Kreira PartnerPortal, SubscriptionPlan, APIUsageLog tablice
- Proširuje APIKey s novim poljima (ne brišemo stare podatke)
"""

import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evalidator', '0002_document_seal'),
    ]

    operations = [

        # ── SubscriptionPlan ──────────────────────────────────────────
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(
                    choices=[('free','Free'),('starter','Starter (€9/mo)'),
                             ('pro','Pro (€29/mo)'),('enterprise','Enterprise')],
                    max_length=20, unique=True)),
                ('display_name', models.CharField(max_length=100)),
                ('price_monthly', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('price_annual',  models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('daily_validation_limit', models.IntegerField(default=100)),
                ('monthly_invoice_limit',  models.IntegerField(default=5)),
                ('monthly_ocr_limit',      models.IntegerField(default=0)),
                ('batch_max_items',        models.IntegerField(default=10)),
                ('has_api_key',      models.BooleanField(default=False)),
                ('has_eidas_seal',   models.BooleanField(default=False)),
                ('has_peppol',       models.BooleanField(default=False)),
                ('has_datev_export', models.BooleanField(default=False)),
                ('has_white_label',  models.BooleanField(default=False)),
                ('has_sla_99_9',     models.BooleanField(default=False)),
                ('pdf_watermark',    models.BooleanField(default=True)),
                ('stripe_price_id_monthly', models.CharField(blank=True, max_length=50)),
                ('stripe_price_id_annual',  models.CharField(blank=True, max_length=50)),
            ],
            options={'db_table': 'evalidator_subscription_plan', 'ordering': ['price_monthly']},
        ),

        # ── PartnerPortal ─────────────────────────────────────────────
        migrations.CreateModel(
            name='PartnerPortal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('portal_type', models.CharField(
                    choices=[('internal','Interni (Fenix V3)'),('reseller','Reseller / White-label'),
                             ('integration','Direktna integracija (API)'),('affiliate','Affiliate (referral)')],
                    default='integration', max_length=20)),
                ('contact_email', models.EmailField(blank=True)),
                ('website',  models.URLField(blank=True)),
                ('master_api_key',  models.CharField(blank=True, max_length=64, unique=True)),
                ('allowed_origins', models.TextField(blank=True)),
                ('monthly_validation_limit', models.IntegerField(default=10000)),
                ('monthly_invoice_limit',    models.IntegerField(default=500)),
                ('monthly_ocr_limit',        models.IntegerField(default=200)),
                ('revenue_share_pct',  models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('stripe_customer_id', models.CharField(blank=True, max_length=50)),
                ('logo_url',      models.URLField(blank=True)),
                ('primary_color', models.CharField(blank=True, default='#C9A84C', max_length=7)),
                ('custom_domain', models.CharField(blank=True, max_length=200)),
                ('is_active',  models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={'db_table': 'evalidator_partner_portal', 'verbose_name': 'Partner Portal'},
        ),

        # ── APIKey — add new fields (keep existing) ───────────────────
        # Rename last_reset → last_daily_reset
        migrations.RenameField('APIKey', 'last_reset', 'last_daily_reset'),
        # Rename daily_limit → remove (replaced by plan FK)
        migrations.RemoveField('APIKey', 'daily_limit'),

        # New fields on APIKey
        migrations.AddField('APIKey', 'key_prefix',
            models.CharField(blank=True, default='', max_length=8)),
        migrations.AddField('APIKey', 'plan',
            models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='api_keys',
                to='evalidator.SubscriptionPlan')),
        migrations.AddField('APIKey', 'portal',
            models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='api_keys',
                to='evalidator.PartnerPortal')),
        migrations.AddField('APIKey', 'billing_cycle',
            models.CharField(choices=[('monthly','Mjesečno'),('annual','Godišnje')],
                             default='monthly', max_length=10)),
        migrations.AddField('APIKey', 'trial_ends_at',
            models.DateTimeField(blank=True, null=True)),
        migrations.AddField('APIKey', 'subscription_start',
            models.DateField(blank=True, null=True)),
        migrations.AddField('APIKey', 'subscription_end',
            models.DateField(blank=True, null=True)),
        migrations.AddField('APIKey', 'stripe_customer_id',
            models.CharField(blank=True, default='', max_length=50)),
        migrations.AddField('APIKey', 'stripe_subscription_id',
            models.CharField(blank=True, default='', max_length=50)),
        migrations.AddField('APIKey', 'monthly_invoices',
            models.IntegerField(default=0)),
        migrations.AddField('APIKey', 'monthly_ocr',
            models.IntegerField(default=0)),
        migrations.AddField('APIKey', 'last_monthly_reset',
            models.DateField(default=datetime.date.today)),
        migrations.AddField('APIKey', 'total_validations',
            models.BigIntegerField(default=0)),
        migrations.AddField('APIKey', 'total_invoices',
            models.BigIntegerField(default=0)),
        migrations.AddField('APIKey', 'is_suspended',
            models.BooleanField(default=False)),
        migrations.AddField('APIKey', 'suspend_reason',
            models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField('APIKey', 'company_name',
            models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField('APIKey', 'company_country',
            models.CharField(blank=True, default='HR', max_length=2)),
        migrations.AddField('APIKey', 'oib',
            models.CharField(blank=True, default='', max_length=11)),
        migrations.AddField('APIKey', 'vat_id',
            models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField('APIKey', 'webhook_url',
            models.URLField(blank=True)),
        migrations.AddField('APIKey', 'last_used_at',
            models.DateTimeField(blank=True, null=True)),

        # Alter plan field name collision (old CharField 'plan')
        migrations.RemoveField('APIKey', 'plan'),
        migrations.AddField('APIKey', 'plan',
            models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='api_keys',
                to='evalidator.SubscriptionPlan')),

        # ── APIUsageLog ───────────────────────────────────────────────
        migrations.CreateModel(
            name='APIUsageLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_key', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='usage_logs',
                    to='evalidator.APIKey')),
                ('portal', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='usage_logs',
                    to='evalidator.PartnerPortal')),
                ('endpoint', models.CharField(
                    choices=[
                        ('validate_oib','Validate OIB'),('validate_vat','Validate VAT ID'),
                        ('validate_iban','Validate IBAN'),('validate_batch','Batch Validation'),
                        ('company_lookup','Company Lookup'),('invoice_gen','Invoice Generate'),
                        ('invoice_ocr','Invoice OCR Import'),('seal_create','Document Seal Create'),
                        ('seal_verify','Seal Verify'),
                    ], max_length=30)),
                ('ip_hash', models.CharField(blank=True, max_length=16)),
                ('country', models.CharField(blank=True, max_length=2)),
                ('response_ms', models.SmallIntegerField(default=0)),
                ('status_code', models.SmallIntegerField(default=200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'evalidator_usage_log',
                'verbose_name': 'Usage Log',
                'indexes': [
                    models.Index(fields=['endpoint', 'created_at'], name='ev_usage_endpoint_idx'),
                    models.Index(fields=['created_at'], name='ev_usage_created_idx'),
                ],
            },
        ),

        # ── Seed default SubscriptionPlans ────────────────────────────
        migrations.RunSQL("""
            INSERT INTO evalidator_subscription_plan
              (code, display_name, price_monthly, price_annual,
               daily_validation_limit, monthly_invoice_limit, monthly_ocr_limit, batch_max_items,
               has_api_key, has_eidas_seal, has_peppol, has_datev_export, has_white_label, has_sla_99_9, pdf_watermark,
               stripe_price_id_monthly, stripe_price_id_annual)
            VALUES
              ('free',       'Free',            0,     0,     100,    5,    0,   10,  false, false, false, false, false, false, true,  '', ''),
              ('starter',    'Starter',         9,    86,    2000,   50,   20,  500, true,  true,  false, false, false, false, false, '', ''),
              ('pro',        'Pro',            29,   278,   20000,  -1,   -1, 1000, true,  true,  true,  true,  false, true,  false, '', ''),
              ('enterprise', 'Enterprise',      0,     0,      -1,  -1,   -1, 9999, true,  true,  true,  true,  true,  true,  false, '', '')
            ON CONFLICT (code) DO NOTHING;
        """, migrations.RunSQL.noop),

        # ── Seed Fenix V3 as internal portal ─────────────────────────
        migrations.RunSQL("""
            INSERT INTO evalidator_partner_portal
              (name, portal_type, contact_email, website, master_api_key,
               monthly_validation_limit, monthly_invoice_limit, monthly_ocr_limit,
               revenue_share_pct, is_active, created_at, notes, logo_url, primary_color, custom_domain, allowed_origins, stripe_customer_id)
            VALUES
              ('Fenix V3', 'internal', 'ivan@konjik.hr', 'https://limit-connect.com',
               'INTERNAL_FENIX_V3_KEY_PLACEHOLDER',
               100000, 5000, 1000, 0, true, NOW(),
               'Interni portal — limit-connect.com korisnici imaju pristup bez naplate',
               '', '#C9A84C', '', 'https://limit-connect.com\nhttps://v3.limit-connect.com', '')
            ON CONFLICT (name) DO NOTHING;
        """, migrations.RunSQL.noop),
    ]
