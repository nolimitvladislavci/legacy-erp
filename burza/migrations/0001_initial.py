from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('companies', '__first__'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [
        migrations.CreateModel(
            name='ProjectLead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('category', models.CharField(max_length=30, default='ostalo',
                    choices=[('kupaonica','Kupaonica'),('plocice','Pločice'),
                             ('vodoinstal','Vodoinstalacije'),('elektrika','Elektrika'),
                             ('grijanje','Grijanje'),('renovacija','Renovacija'),
                             ('gradnja','Gradnja'),('fasada','Fasada'),('ostalo','Ostalo')])),
                ('location', models.CharField(max_length=200)),
                ('budget_from', models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
                ('budget_to', models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
                ('desired_start', models.DateField(null=True, blank=True)),
                ('contact_name', models.CharField(max_length=100)),
                ('contact_phone', models.CharField(max_length=30)),
                ('contact_email', models.EmailField(blank=True)),
                ('status', models.CharField(max_length=20, db_index=True, default='NOVI_UPIT',
                    choices=[('NOVI_UPIT','Novi upit'),('INTERNA_PROCJENA','Interna procjena'),
                             ('NA_BURZI','Na burzi'),('PREUZETO','Preuzeto')])),
                ('internal_notes', models.TextField(blank=True)),
                ('is_public', models.BooleanField(default=False)),
                ('taken_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_leads', to='auth.user')),
                ('company', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='project_leads', to='companies.company')),
                ('created_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_leads', to='auth.user')),
                ('taken_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taken_leads', to='companies.company')),
                ('taken_by_user', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taken_leads', to='auth.user')),
            ],
            options={'verbose_name':'Projektni upit','verbose_name_plural':'Projektni upiti','ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='LeadActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=200)),
                ('old_status', models.CharField(max_length=20, blank=True)),
                ('new_status', models.CharField(max_length=20, blank=True)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='burza.projectlead')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
            ],
            options={'ordering':['-created_at']},
        ),
    ]
