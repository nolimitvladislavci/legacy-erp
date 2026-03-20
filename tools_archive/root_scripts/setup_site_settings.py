import os

BASE_DIR = '/var/www/fina-connect'
WEBSITE_DIR = os.path.join(BASE_DIR, 'website')
MODELS_FILE = os.path.join(WEBSITE_DIR, 'models.py')
ADMIN_FILE = os.path.join(WEBSITE_DIR, 'admin.py')

# 1. Dodavanje SiteSettings u website/models.py
with open(MODELS_FILE, 'r', encoding='utf-8') as f:
    models_content = f.read()

if "class SiteSettings" not in models_content:
    new_model = """
class SiteSettings(models.Model):
    \"\"\"Globalne postavke javne web stranice (Kontakt, Godina, itd.)\"\"\"
    company_name = models.CharField(max_length=100, default="Visković Group", verbose_name="Naziv tvrtke")
    founded_year = models.IntegerField(default=2018, verbose_name="Godina osnivanja (DE)")
    phone_1_name = models.CharField(max_length=50, default="Dragan", verbose_name="Kontakt 1 Ime")
    phone_1_number = models.CharField(max_length=30, default="+4917684397173", verbose_name="Kontakt 1 Broj")
    phone_2_name = models.CharField(max_length=50, default="Nikša", verbose_name="Kontakt 2 Ime")
    phone_2_number = models.CharField(max_length=30, default="+4915234209056", verbose_name="Kontakt 2 Broj")
    email = models.EmailField(default="viskovic.bau@gmail.com", verbose_name="Glavni E-mail")
    
    class Meta:
        verbose_name = "Postavke Weba"
        verbose_name_plural = "Postavke Weba"

    def __str__(self):
        return f"Postavke: {self.company_name}"
"""
    with open(MODELS_FILE, 'a', encoding='utf-8') as f:
        f.write(new_model)

# 2. Registracija u admin.py
with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
    admin_content = f.read()

if "SiteSettings" not in admin_content:
    new_admin = """
from .models import SiteSettings
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'founded_year', 'email']
    # Kako bismo osigurali da uvijek postoji samo jedan unos
    def has_add_permission(self, request):
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)
"""
    with open(ADMIN_FILE, 'a', encoding='utf-8') as f:
        f.write(new_admin)

# 3. Izrada migracija i migriranje
os.system("python3 manage.py makemigrations website")
os.system("python3 manage.py migrate website")
print("✅ BAZA JE SPREMNA! Model SiteSettings je dodan.")
