import os

URLS_FILE = '/var/www/fina-connect/website/urls.py'

print("⏳ Čistim i prepisujem ruter (urls.py)...")

uredan_ruter = """from django.urls import path
from . import views
from . import cms_views

app_name = 'website'

urlpatterns = [
    # CUSTOM ENTERPRISE CMS RUTE (Ispravljena imena funkcija)
    path('cms/gallery/', cms_views.cms_gallery, name='cms_gallery'),
    path('cms/gallery/toggle/<int:id>/', cms_views.toggle_img, name='toggle_img'),

    # POSTOJEĆE RUTE
    path('', views.homepage, name='homepage'),
    path('bau/', views.bau_page, name='bau_page'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('hitna-intervencija/', views.hitna_intervencija, name='hitna_intervencija'),
    path('hitna-intervencija/hvala/', views.hitna_hvala, name='hitna_hvala'),
    path('video-galerija/', views.video_galerija, name='video_galerija'),
    path('hr/', views.viskovic_hr, name='viskovic_hr'),
]
"""

with open(URLS_FILE, 'w', encoding='utf-8') as f:
    f.write(uredan_ruter)

os.system("supervisorctl restart fina-connect")
print("✅ RUTER JE POPRAVLJEN! Sustav je ponovno online.")
