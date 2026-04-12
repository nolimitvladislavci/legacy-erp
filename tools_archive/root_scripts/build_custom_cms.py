import os
import shutil
import re

BASE_DIR = '/var/www/fina-connect'
WEB_URLS = os.path.join(BASE_DIR, 'website/urls.py')
WEB_CMS_HTML = os.path.join(BASE_DIR, 'website/templates/website/index.html')
CMS_VIEWS_FILE = os.path.join(BASE_DIR, 'website/cms_views.py')
CMS_TEMPLATE_DIR = os.path.join(BASE_DIR, 'website/templates/website/cms')

# 1. Sigurnosni backup i priprema direktorija
print("⏳ 1/5 Pripremam strukturu i backupe...")
if not os.path.exists(CMS_TEMPLATE_DIR):
    os.makedirs(CMS_TEMPLATE_DIR)

if os.path.exists(WEB_URLS): shutil.copy2(WEB_URLS, WEB_URLS + '.bak_custom_cms')
if os.path.exists(WEB_CMS_HTML): shutil.copy2(WEB_CMS_HTML, WEB_CMS_HTML + '.bak_custom_cms')


# 2. Kreiranje Backend Logike (cms_views.py)
print("⏳ 2/5 Kreiram Custom CMS Backend logiku...")
cms_views_code = """from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _
from .models import GalleryImage, VideoGallery, HitnaIntervencija

def is_admin(user):
    return user.is_superuser or (hasattr(user, 'profile') and user.profile.role in ['company_admin', 'superadmin'])

@login_required
@user_passes_test(is_admin)
def custom_cms_gallery(request):
    \"\"\"Enterprise kontrolna ploča za galeriju s višejezičnim formama\"\"\"
    if request.method == 'POST':
        # Upload nove slike
        image = request.FILES.get('image')
        category = request.POST.get('category', 'bau')
        caption_de = request.POST.get('caption_de', '')
        caption_hr = request.POST.get('caption_hr', '')
        caption_en = request.POST.get('caption_en', '')
        
        if image:
            GalleryImage.objects.create(
                image=image,
                category=category,
                caption_de=caption_de,
                caption_hr=caption_hr,
                caption_en=caption_en,
                is_active=True,
                order=0
            )
            messages.success(request, _('Slika je uspješno dodana na javni portal!'))
        return redirect('website:custom_cms_gallery')

    images = GalleryImage.objects.all().order_by('-id')
    return render(request, 'website/cms/gallery_manager.html', {'images': images})

@login_required
@user_passes_test(is_admin)
def toggle_gallery_status(request, img_id):
    \"\"\"AJAX funkcija za paljenje/gašenje slike na webu\"\"\"
    if request.method == 'POST':
        try:
            img = GalleryImage.objects.get(id=img_id)
            img.is_active = not img.is_active
            img.save()
            return JsonResponse({'ok': True, 'is_active': img.is_active})
        except GalleryImage.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Slika nije pronađena'}, status=404)
    return JsonResponse({'ok': False}, status=400)
"""
with open(CMS_VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(cms_views_code)


# 3. Dodavanje Ruti u urls.py
print("⏳ 3/5 Dodajem rute za Custom CMS...")
with open(WEB_URLS, 'r', encoding='utf-8') as f:
    urls_code = f.read()

if "path('cms/gallery/'" not in urls_code:
    # Uvozimo nove poglede na vrhu ako ne postoje
    if "from . import cms_views" not in urls_code:
        urls_code = urls_code.replace("from . import views", "from . import views\nfrom . import cms_views")
    
    nove_rute = """
    # CUSTOM ENTERPRISE CMS RUTE
    path('cms/gallery/', cms_views.custom_cms_gallery, name='custom_cms_gallery'),
    path('cms/gallery/toggle/<int:img_id>/', cms_views.toggle_gallery_status, name='toggle_gallery_status'),
"""
    # Ubacujemo unutar urlpatterns = [
    urls_code = urls_code.replace("urlpatterns = [", "urlpatterns = [" + nove_rute)
    with open(WEB_URLS, 'w', encoding='utf-8') as f:
        f.write(urls_code)


# 4. Mijenjanje linkova na CMS Dashboardu (Brišemo /admin/)
print("⏳ 4/5 Preusmjeravam CMS Dashboard na nove Enterprise forme...")
with open(WEB_CMS_HTML, 'r', encoding='utf-8') as f:
    cms_html = f.read()

cms_html = cms_html.replace('href="/admin/website/galleryimage/"', 'href="{% url \'website:custom_cms_gallery\' %}"')
with open(WEB_CMS_HTML, 'w', encoding='utf-8') as f:
    f.write(cms_html)


# 5. Kreiranje Frontend Dizajna (gallery_manager.html)
print("⏳ 5/5 Kreiram Enterprise višejezično sučelje za Galeriju...")
gallery_html = """{% extends 'base.html' %}
{% load i18n %}

{% block title %}Galerie Manager | Visković CMS{% endblock %}
{% block page_title %}Upravljanje Galerijom{% endblock %}

{% block content %}
<style>
    .cms-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 24px; }
    .cms-title { font-family: 'Barlow Condensed', sans-serif; font-size: 1.8rem; color: var(--gold); letter-spacing: 1px; text-transform: uppercase; margin: 0; }
    
    .form-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 30px; }
    .form-card h3 { color: var(--text); font-size: 1.1rem; margin-bottom: 20px; font-weight: 700; border-bottom: 1px dashed var(--border); padding-bottom: 10px; }
    
    .form-label { color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 6px; display: block; }
    .custom-input { width: 100%; background: var(--black); border: 1px solid var(--border); color: var(--text); padding: 12px; border-radius: 8px; margin-bottom: 16px; transition: border-color 0.3s; }
    .custom-input:focus { border-color: var(--gold); outline: none; }
    
    .lang-badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 800; margin-right: 8px; }
    .bg-de { background: #3b82f6; color: white; }
    .bg-hr { background: #ef4444; color: white; }
    .bg-en { background: #10b981; color: white; }

    .submit-btn { background: var(--gold); color: #000; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; width: 100%; transition: all 0.3s; }
    .submit-btn:hover { background: var(--gold-dim); }
    .submit-btn:disabled { opacity: 0.7; cursor: not-allowed; }

    .table-dark-custom { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--surface); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
    .table-dark-custom th { background: var(--surface2); color: var(--text-dim); font-weight: 600; text-transform: uppercase; font-size: 0.8rem; padding: 16px; text-align: left; letter-spacing: 1px; }
    .table-dark-custom td { padding: 16px; border-top: 1px solid var(--border); vertical-align: middle; }
    .table-dark-custom img { width: 60px; height: 60px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border); }
    
    /* Toggle Switch */
    .switch { position: relative; display: inline-block; width: 46px; height: 24px; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--surface2); transition: .4s; border-radius: 34px; border: 1px solid var(--border); }
    .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 4px; bottom: 3px; background-color: var(--text-dim); transition: .4s; border-radius: 50%; }
    input:checked + .slider { background-color: rgba(34, 197, 94, 0.2); border-color: #22c55e; }
    input:checked + .slider:before { transform: translateX(20px); background-color: #22c55e; }
    
    .status-text { font-size: 0.8rem; font-weight: 700; margin-left: 10px; vertical-align: text-bottom; }
    .status-active { color: #22c55e; }
    .status-inactive { color: var(--text-dim); }
</style>

<div class="cms-header">
    <h1 class="cms-title"><i class="fas fa-images"></i> Enterprise Galerija</h1>
    <a href="{% url 'website:admin_panel' %}" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left"></i> Natrag na CMS Hub</a>
</div>

{% if messages %}
    {% for msg in messages %}
        <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid #22c55e; color: #22c55e; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-weight: 600;">
            <i class="fas fa-check-circle"></i> {{ msg }}
        </div>
    {% endfor %}
{% endif %}

<div class="row">
    <div class="col-lg-4">
        <div class="form-card">
            <h3><i class="fas fa-plus-circle text-warning"></i> Dodaj novu referencu</h3>
            <form method="post" enctype="multipart/form-data" id="uploadForm">
                {% csrf_token %}
                
                <label class="form-label">Odaberi sliku *</label>
                <input type="file" name="image" class="custom-input" required accept="image/*">
                
                <label class="form-label">Kategorija (Odjel)</label>
                <select name="category" class="custom-input">
                    <option value="bau">Visković BAU</option>
                    <option value="najam">VG Najam</option>
                    <option value="webshop">VG Shop</option>
                </select>
                
                <div style="height: 10px;"></div>
                <h4 style="font-size: 0.85rem; color: var(--gold); margin-bottom: 15px; text-transform: uppercase;">Višejezični Naslovi</h4>
                
                <label class="form-label"><span class="lang-badge bg-de">DE</span> Naslov (Njemački) *</label>
                <input type="text" name="caption_de" class="custom-input" placeholder="npr. Badezimmer Sanierung" required>
                
                <label class="form-label"><span class="lang-badge bg-hr">HR</span> Naslov (Hrvatski)</label>
                <input type="text" name="caption_hr" class="custom-input" placeholder="npr. Sanacija Kupaonice">
                
                <label class="form-label"><span class="lang-badge bg-en">EN</span> Naslov (Engleski)</label>
                <input type="text" name="caption_en" class="custom-input" placeholder="npr. Bathroom Renovation">
                
                <button type="submit" class="submit-btn" id="submitBtn">
                    <i class="fas fa-cloud-upload-alt"></i> Spremi i Objavi
                </button>
            </form>
        </div>
    </div>

    <div class="col-lg-8">
        <div style="overflow-x: auto;">
            <table class="table-dark-custom">
                <thead>
                    <tr>
                        <th width="80">Slika</th>
                        <th>Naslovi (Višejezično)</th>
                        <th>Kategorija</th>
                        <th class="text-center">Javno Vidljivo</th>
                    </tr>
                </thead>
                <tbody>
                    {% for img in images %}
                    <tr>
                        <td>
                            {% if img.image %}
                                <a href="{{ img.image.url }}" target="_blank"><img src="{{ img.image.url }}" alt="Slika"></a>
                            {% endif %}
                        </td>
                        <td>
                            <div style="font-weight: 700; color: var(--text);">{{ img.caption_de|default:"-" }} <span style="font-size: 0.7rem; color: #3b82f6;">(DE)</span></div>
                            <div style="font-size: 0.85rem; color: var(--text-dim); margin-top: 4px;">{{ img.caption_hr|default:"-" }} <span style="font-size: 0.7rem; color: #ef4444;">(HR)</span></div>
                        </td>
                        <td>
                            <span style="background: rgba(201, 168, 76, 0.1); color: var(--gold); padding: 4px 10px; border-radius: 99px; font-size: 0.8rem; font-weight: 700;">
                                {{ img.get_category_display|default:img.category|upper }}
                            </span>
                        </td>
                        <td class="text-center">
                            <label class="switch">
                                <input type="checkbox" onchange="toggleStatus(this, {{ img.id }})" {% if img.is_active %}checked{% endif %}>
                                <span class="slider"></span>
                            </label>
                            <span class="status-text {% if img.is_active %}status-active{% else %}status-inactive{% endif %}" id="status-text-{{ img.id }}">
                                {% if img.is_active %}Aktivno{% else %}Skriveno{% endif %}
                            </span>
                        </td>
                    </tr>
                    {% empty %}
                    <tr>
                        <td colspan="4" class="text-center" style="padding: 40px; color: var(--text-dim);">
                            <i class="fas fa-image fa-2x mb-3" style="opacity: 0.3;"></i><br>Baza je trenutno prazna.
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
    // 1. Loading stanje na formi
    document.getElementById('uploadForm').addEventListener('submit', function() {
        const btn = document.getElementById('submitBtn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Zapisivanje u bazu...';
    });

    // 2. AJAX za paljenje/gašenje bez refresha
    function toggleStatus(checkbox, imgId) {
        const textSpan = document.getElementById('status-text-' + imgId);
        const originalText = textSpan.innerHTML;
        const originalColor = textSpan.className;
        
        textSpan.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        checkbox.disabled = true;

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');

        fetch(`/website/cms/gallery/toggle/${imgId}/`, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            checkbox.disabled = false;
            if(data.ok) {
                if(data.is_active) {
                    textSpan.innerHTML = 'Aktivno';
                    textSpan.className = 'status-text status-active';
                } else {
                    textSpan.innerHTML = 'Skriveno';
                    textSpan.className = 'status-text status-inactive';
                }
            } else {
                alert('Greška pri komunikaciji s bazom.');
                checkbox.checked = !checkbox.checked;
                textSpan.innerHTML = originalText;
                textSpan.className = originalColor;
            }
        })
        .catch(error => {
            checkbox.disabled = false;
            checkbox.checked = !checkbox.checked;
            textSpan.innerHTML = originalText;
            textSpan.className = originalColor;
            alert('Mrežna greška.');
        });
    }
</script>
{% endblock %}
"""
with open(os.path.join(CMS_TEMPLATE_DIR, 'gallery_manager.html'), 'w', encoding='utf-8') as f:
    f.write(gallery_html)

os.system("chown -R www-data:www-data /var/www/fina-connect/")
os.system("supervisorctl restart fina-connect")

print("✅ CUSTOM CMS ZA GALERIJU JE SPREMAN! Višejezične forme su aktivne.")
