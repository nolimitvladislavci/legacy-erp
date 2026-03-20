import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIModulePermission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('module', models.CharField(choices=[
                    ('accounts', 'Korisnici'), ('appointments', 'Termini'),
                    ('calculator', 'Kalkulator'), ('companies', 'Tvrtke'),
                    ('documents', 'Dokumenti'), ('eracun', 'e-Račun'),
                    ('finance', 'Financije'), ('fitness', 'Fitness'),
                    ('insurance', 'Osiguranje'), ('inventory', 'Skladište'),
                    ('invoicing', 'Fakturiranje'), ('partners', 'Partneri'),
                    ('payments', 'Plaćanja'), ('pos', 'POS Blagajna'),
                    ('projects', 'Projekti'), ('rental', 'Najam / Hotel'),
                    ('smart_import', 'Smart Import (AIP)'), ('synesis', 'Synesis'),
                    ('website', 'Web stranica'), ('webshop', 'Webshop'),
                    ('worktime', 'Radno vrijeme'), ('work_orders', 'Radni nalozi'),
                ], max_length=50, verbose_name='Modul')),
                ('access_level', models.IntegerField(choices=[
                    (0, 'Isključeno'), (1, 'Samo čitanje'),
                    (2, 'Asistiran (odobrenje)'), (3, 'Autonoman'),
                ], default=0, verbose_name='Razina pristupa')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notes', models.TextField(blank=True, verbose_name='Napomena')),
                ('company', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='ai_permissions', to='companies.company',
                    verbose_name='Tvrtka', help_text='Prazno = globalno (sve tvrtke)'
                )),
                ('updated_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL, verbose_name='Ažurirao'
                )),
            ],
            options={
                'db_table': 'ai_module_permission',
                'verbose_name': 'AI dozvola modula',
                'verbose_name_plural': 'AI dozvole modula',
                'ordering': ['module'],
                'unique_together': {('company', 'module')},
            },
        ),
        migrations.CreateModel(
            name='PendingAIAction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('module', models.CharField(max_length=50, verbose_name='Modul')),
                ('action_type', models.CharField(max_length=50, verbose_name='Tip akcije',
                    help_text='npr. create, update, delete, send')),
                ('description', models.TextField(verbose_name='Opis akcije')),
                ('payload', models.JSONField(default=dict, verbose_name='Podaci',
                    help_text='JSON s detaljima akcije za izvršenje')),
                ('status', models.CharField(choices=[
                    ('pending', 'Čeka odobrenje'), ('approved', 'Odobreno'),
                    ('rejected', 'Odbijeno'), ('executed', 'Izvršeno'), ('expired', 'Isteklo'),
                ], default='pending', max_length=20, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_note', models.TextField(blank=True, verbose_name='Komentar')),
                ('result', models.JSONField(blank=True, default=dict, verbose_name='Rezultat izvršenja')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pending_ai_actions', to='companies.company',
                    verbose_name='Tvrtka'
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_ai_actions', to=settings.AUTH_USER_MODEL,
                    verbose_name='Pregledao'
                )),
            ],
            options={
                'db_table': 'ai_pending_action',
                'verbose_name': 'AI čekajuća akcija',
                'verbose_name_plural': 'AI čekajuće akcije',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AIActionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('module', models.CharField(max_length=50, verbose_name='Modul')),
                ('action_type', models.CharField(max_length=50, verbose_name='Tip')),
                ('access_level', models.IntegerField(choices=[
                    (0, 'Isključeno'), (1, 'Samo čitanje'),
                    (2, 'Asistiran (odobrenje)'), (3, 'Autonoman'),
                ], verbose_name='Razina')),
                ('outcome', models.CharField(choices=[
                    ('allowed', 'Dopušteno'), ('blocked', 'Blokirano'),
                    ('queued', 'U redu čekanja'), ('executed', 'Izvršeno'),
                    ('failed', 'Neuspješno'),
                ], max_length=20, verbose_name='Ishod')),
                ('details', models.JSONField(blank=True, default=dict, verbose_name='Detalji')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='companies.company', verbose_name='Tvrtka'
                )),
                ('user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL, verbose_name='Korisnik'
                )),
            ],
            options={
                'db_table': 'ai_action_log',
                'verbose_name': 'AI log',
                'verbose_name_plural': 'AI logovi',
                'ordering': ['-timestamp'],
            },
        ),
    ]
