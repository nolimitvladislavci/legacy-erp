import os

print("\n" + "="*50)
print("🔍 ISPIS WORKTIME MODELA")
print("="*50)
os.system("cat /var/www/fina-connect/worktime/models.py")

print("\n" + "="*50)
print("🔍 ISPIS TRENUTNOG PARTNER VIEWS-a")
print("="*50)
os.system("sed -n '/def partner_dashboard/,/return render/p' /var/www/fina-connect/core/views.py")

print("\n" + "="*50)
