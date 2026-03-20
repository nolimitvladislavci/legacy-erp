import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile
from companies.models import Company

def update_users_smart():
    print(">>> ZAPOČINJEM PAMETNO POSTAVLJANJE ULOGA I LOZINKI...")
    
    new_password = "s5Jtkn66!"
    main_company = Company.objects.first() # Uzimamo tvoju glavnu tvrtku
    
    if not main_company:
        print("! Greška: Tvrtka nije pronađena u bazi.")
        return

    users = User.objects.all()
    count = 0

    for user in users:
        # 1. Postavljanje lozinke za sve (osim ako ne želiš zadržati svoju admin lozinku)
        user.set_password(new_password)
        user.save()
        
        # 2. Provjera je li korisnik admin ili radnik
        # Ako je superuser ili staff u Djangu, u profilu mu pišemo 'admin'
        if user.is_superuser or user.is_staff:
            assigned_role = 'admin'
        else:
            assigned_role = 'worker'
        
        # 3. Sinkronizacija profila
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.company = main_company
        profile.role = assigned_role
        profile.save()
        
        count += 1
        print(f"✓ {user.username} -> Dodijeljena uloga: {assigned_role}")

    print(f"==================================================")
    print(f" USPJEH: {count} korisnika je sinkronizirano.")
    print(f" Svi korisnici sada koriste lozinku: {new_password}")
    print(f"==================================================")

if __name__ == '__main__':
    update_users_smart()
