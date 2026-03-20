import os

print("🚀 Otključavanje Resursa i Termina u Django Adminu...")

admin_path = '/var/www/fina-connect/appointments/admin.py'

if os.path.exists(admin_path):
    with open(admin_path, 'r', encoding='utf-8') as f:
        content = f.read()

    admin_additions = ""
    
    # Ako BookingResource nije registriran, dodajemo ga
    if "BookingResourceAdmin" not in content:
        admin_additions += """
from .models import BookingResource, Appointment

@admin.register(BookingResource)
class BookingResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'resource_type', 'is_active')
    list_filter = ('resource_type', 'is_active')
    search_fields = ('name',)
"""
    
    # Ako Appointment (Sami termini) nisu u adminu, dodajemo i njih za lakši pregled
    if "AppointmentAdmin" not in content:
        admin_additions += """
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'start_time', 'appointment_type', 'resource', 'status')
    list_filter = ('appointment_type', 'status', 'resource')
    search_fields = ('title',)
"""

    if admin_additions:
        with open(admin_path, 'a', encoding='utf-8') as f:
            f.write(admin_additions)
        print("✅ Modeli BookingResource i Appointment uspješno dodani u Admin!")
    else:
        print("⏩ Modeli su već registrirani.")

os.system("supervisorctl restart fina-connect")
print("✨ Sustav osvježen. Vrati se u Django Admin i osvježi stranicu!")
