import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
print("✅ Django se uspješno inicijalizirao.")

try:
    from projects.models import Project
    print("✅ Project model učitan.")
    from appointments.models import Appointment
    print("✅ Appointment model učitan.")
except Exception as e:
    print(f"❌ GREŠKA PRI UČITAVANJU: {e}")
