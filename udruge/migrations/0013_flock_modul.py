from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('udruge', '0012_golubar_modul'),
    ]

    operations = [
        migrations.CreateModel(
            name='Flock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('naziv', models.CharField(max_length=200, verbose_name='Naziv jata')),
                ('vrsta', models.CharField(choices=[('kokos', 'Kokoš'), ('prepelica', 'Prepelica'), ('patka', 'Patka'), ('guska', 'Guska')], max_length=15)),
                ('pasmina', models.CharField(blank=True, max_length=100, verbose_name='Pasmina')),
                ('broj_komada', models.PositiveIntegerField(verbose_name='Broj komada')),
                ('datum_nabave', models.DateField(verbose_name='Datum nabave')),
                ('tip_uzgoja', models.CharField(choices=[('slobodni', 'Slobodni uzgoj'), ('kavezni', 'Kavezni uzgoj'), ('organski', 'Organski uzgoj')], default='slobodni', max_length=15)),
                ('objekt', models.CharField(blank=True, max_length=200, verbose_name='Objekt / kokošinjac')),
                ('napomena', models.TextField(blank=True)),
                ('aktivan', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flockovi', to='companies.company')),
            ],
            options={
                'verbose_name': 'Jato peradi',
                'verbose_name_plural': 'Jata peradi',
                'db_table': 'udruge_flock',
                'ordering': ['-datum_nabave'],
            },
        ),
        migrations.CreateModel(
            name='EggRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datum', models.DateField(verbose_name='Datum')),
                ('broj_jaja', models.PositiveIntegerField(verbose_name='Broj jaja')),
                ('broken', models.PositiveIntegerField(default=0, verbose_name='Polomljena')),
                ('sold', models.PositiveIntegerField(default=0, verbose_name='Prodano')),
                ('za_prodaju', models.BooleanField(default=False, verbose_name='Za tržnicu')),
                ('cijena_eur', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Cijena (EUR/kom)')),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('flock', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='egg_records', to='udruge.flock')),
            ],
            options={
                'verbose_name': 'Zapis nesenja',
                'verbose_name_plural': 'Zapisi nesenja',
                'db_table': 'udruge_egg_record',
                'ordering': ['-datum'],
                'unique_together': {('flock', 'datum')},
            },
        ),
        migrations.CreateModel(
            name='FlockHealthRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vrsta_tretmana', models.CharField(choices=[('cijepljenje', 'Cijepljenje'), ('antiparazit', 'Antiparazitik'), ('antibiotik', 'Antibiotik'), ('vitamin', 'Vitamini / dodaci'), ('vet_pregled', 'Veterinarski pregled'), ('ostalo', 'Ostalo')], max_length=15)),
                ('datum', models.DateField()),
                ('lijek', models.CharField(blank=True, max_length=200, verbose_name='Lijek / preparat')),
                ('doza', models.CharField(blank=True, max_length=100)),
                ('veterinar', models.CharField(blank=True, max_length=200)),
                ('karenca_dana', models.PositiveIntegerField(blank=True, help_text='Koliko dana jaja nisu za prodaju', null=True, verbose_name='Karenca (dana)')),
                ('napomena', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('flock', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zdravstveni_zapisi', to='udruge.flock')),
            ],
            options={
                'verbose_name': 'Zdravstveni zapis jata',
                'verbose_name_plural': 'Zdravstveni zapisi jata',
                'db_table': 'udruge_flock_health',
                'ordering': ['-datum'],
            },
        ),
        migrations.CreateModel(
            name='FlockMortality',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datum', models.DateField()),
                ('broj_uginulih', models.PositiveIntegerField(verbose_name='Broj uginulih')),
                ('razlog', models.CharField(blank=True, max_length=200, verbose_name='Razlog / uzrok')),
                ('napomena', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('flock', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mortaliteti', to='udruge.flock')),
            ],
            options={
                'verbose_name': 'Uginuće u jatu',
                'verbose_name_plural': 'Uginuća u jatu',
                'db_table': 'udruge_flock_mortality',
                'ordering': ['-datum'],
            },
        ),
    ]
