import os
import shutil
import re

print("🚀 FAZA 1: Nadogradnja baze s Uslugama i Radnim Vremenom...")

models_path = '/var/www/fina-connect/appointments/models.py'
admin_path = '/var/www/fina-connect/appointments/admin.py'

# 1. BACKUP
for file_path in [models_path, admin_path]:
    if os.path.exists(file_path):
        shutil.copy2(file_path, f"{file_path}.bak")
print("📦 Sigurnosni backupi kreirani.")

# 2. DODAVANJE NOVIH MODELA (models.py)
with open(models_path, 'r', encoding='utf-8') as f:
    models_content = f.read()

new_models = ""
if "class BookingService" not in models_content:
    new_models += """
class BookingService(models.Model):
    name = models.CharField(max_length=150, verbose_name='Naziv usluge (npr. Kontrola vida, Dijagnostika)')
    description = models.TextField(blank=True, verbose_name='Opis usluge')
    duration = models.DurationField(verbose_name='Trajanje usluge (HH:MM:SS)')
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Cijena (EUR)')
    resource_type = models.CharField(max_length=50, choices=BookingResource.RESOURCE_TYPES, default='ljudstvo', verbose_name='Vezano za tip resursa')
    is_active = models.BooleanField(default=True, verbose_name='Aktivno za javnost')

    class Meta:
        verbose_name = 'Usluga'
        verbose_name_plural = 'Usluge'

    def __str__(self):
        return f"{self.name} ({self.duration})"
"""

if "class WorkingHours" not in models_content:
    new_models += """
class WorkingHours(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Ponedjeljak'), (1, 'Utorak'), (2, 'Srijeda'), 
        (3, 'Četvrtak'), (4, 'Petak'), (5, 'Subota'), (6, 'Nedjelja')
    ]
    resource = models.ForeignKey(BookingResource, on_delete=models.CASCADE, related_name='working_hours', verbose_name='Resurs')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK, verbose_name='Dan u tjednu')
    start_time = models.TimeField(verbose_name='Početak rada')
    end_time = models.TimeField(verbose_name='Kraj rada')
    is_day_off = models.BooleanField(default=False, verbose_name='Neradni dan')

    class Meta:
        verbose_name = 'Radno vrijeme'
        verbose_name_plural = 'Radna vremena'
        unique_together = ('resource', 'day_of_week')
        ordering = ['resource', 'day_of_week']

    def __str__(self):
        if self.is_day_off:
            return f"{self.resource.name} - {self.get_day_of_week_display()} (Slobodno)"
        return f"{self.resource.name} - {self.get_day_of_week_display()} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"
"""

# Povezivanje Appointmenta s Uslugom (Kirurški regex)
if "service = models.ForeignKey" not in models_content:
    appointment_injection = "    service = models.ForeignKey('BookingService', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Odabrana usluga')\n"
    models_content = re.sub(r'(class Appointment\(models\.Model\):.*?)(    appointment_type =)', r'\1' + appointment_injection + r'\2', models_content, flags=re.DOTALL)

if new_models:
    with open(models_path, 'w', encoding='utf-8') as f:
        f.write(models_content + "\n" + new_models)
    print("✅ Modeli BookingService i WorkingHours dodani.")

# 3. DODAVANJE U DJANGO ADMIN (admin.py)
with open(admin_path, 'r', encoding='utf-8') as f:
    admin_content = f.read()

if "BookingServiceAdmin" not in admin_content:
    # Moramo dodati import za nove modele
    admin_content = admin_content.replace("from .models import ", "from .models import BookingService, WorkingHours, ")
    
    admin_additions = """
@admin.register(BookingService)
class BookingServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration', 'price', 'resource_type', 'is_active')
    list_filter = ('resource_type', 'is_active')
    search_fields = ('name',)

@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ('resource', 'get_day_of_week_display', 'start_time', 'end_time', 'is_day_off')
    list_filter = ('resource', 'day_of_week', 'is_day_off')
"""
    with open(admin_path, 'a', encoding='utf-8') as f:
        f.write(admin_additions)
    print("✅ Modeli registrirani u Django Adminu.")

# 4. MIGRACIJE I DOZVOLE
os.system("/var/www/fina-connect/venv/bin/python /var/www/fina-connect/manage.py makemigrations appointments")
os.system("/var/www/fina-connect/venv/bin/python /var/www/fina-connect/manage.py migrate")
os.system("chown -R www-data:www-data /var/www/fina-connect/appointments")
os.system("supervisorctl restart fina-connect")

print("✨ FAZA 1 završena. Baza je spremna za javni booking sustav!")
