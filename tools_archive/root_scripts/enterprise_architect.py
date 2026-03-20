import os
import re

BASE_DIR = '/var/www/fina-connect'

print("⏳ 1/5 Popravljam BAU stranicu (Prisilno povlačenje slika)...")
views_path = os.path.join(BASE_DIR, 'website/views.py')
with open(views_path, 'r', encoding='utf-8') as f:
    v_code = f.read()

# Python-level filter koji je 100% otporan na greške u bazi
new_bau = """def bau_page(request):
    from website.models import GalleryImage, VideoGallery
    from django.shortcuts import render
    media_items = []
    try:
        # Prikupi slike i filtriraj na razini Pythona
        for s in GalleryImage.objects.filter(is_active=True):
            cat = str(getattr(s, 'category', getattr(s, 'kategorija', ''))).lower()
            if 'bau' in cat or 'viskovi' in cat:
                if s.image:
                    title = getattr(s, 'caption_de', getattr(s, 'caption_hr', getattr(s, 'title', 'Referenz')))
                    media_items.append({'type': 'image', 'url': s.image.url, 'title': title})
        
        # Prikupi videe i filtriraj
        for v in VideoGallery.objects.filter(is_active=True):
            cat = str(getattr(v, 'kategorija', getattr(v, 'category', ''))).lower()
            if 'bau' in cat or 'viskovi' in cat:
                if getattr(v, 'video_file', None):
                    title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', getattr(v, 'title', 'Video')))
                    media_items.append({'type': 'video_file', 'url': v.video_file.url, 'title': title})
                elif getattr(v, 'embed_url', None):
                    title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', getattr(v, 'title', 'Video')))
                    media_items.append({'type': 'video_embed', 'url': v.embed_url, 'title': title})
    except Exception as e:
        print("Galerija Error:", e)
    return render(request, 'website/bau.html', {'media_items': media_items})
"""
v_code = re.sub(r'def bau_page\(request\):.*?return render.*?\}\)', new_bau, v_code, flags=re.DOTALL)
with open(views_path, 'w', encoding='utf-8') as f:
    f.write(v_code)


print("⏳ 2/5 Ubrizgavam logiku u sve BAU HTML predloške...")
bau_snippet = """<div class="gallery-grid">
        {% if media_items %}
            {% for item in media_items %}
            <div class="gallery-item" style="position:relative; border-radius:12px; overflow:hidden; border:1px solid var(--border); aspect-ratio:4/3;">
                {% if item.type == 'image' %}
                    <img src="{{ item.url }}" alt="{{ item.title }}" style="width:100%; height:100%; object-fit:cover;">
                {% elif item.type == 'video_file' %}
                    <video width="100%" height="100%" style="object-fit:cover; background:#000;" controls muted playsinline preload="metadata"><source src="{{ item.url }}" type="video/mp4"></video>
                {% elif item.type == 'video_embed' %}
                    <iframe src="{{ item.url }}" width="100%" height="100%" style="border:none;" allowfullscreen></iframe>
                {% endif %}
                <div class="gallery-overlay" style="position:absolute; inset:0; background:linear-gradient(to top, rgba(10,10,10,0.9), transparent); pointer-events:none; display:flex; align-items:flex-end; padding:20px;">
                    <div style="color:var(--gold); font-family:'Barlow Condensed', sans-serif; font-size:1.3rem; text-transform:uppercase; letter-spacing:2px;">{{ item.title }}</div>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div style="grid-column: 1 / -1; text-align: center; color: var(--gold); padding: 60px; border: 1px dashed var(--border); border-radius: 12px;">
                <i class="fas fa-camera fa-2x mb-3"></i>
                <p>Nema aktivnih slika za BAU odjel.</p>
            </div>
        {% endif %}
    </div>"""

# Pretražujemo cijeli server i mijenjamo SVAKI bau.html da osiguramo prikaz
for root_dir, _, files in os.walk(BASE_DIR):
    if 'bau.html' in files:
        p = os.path.join(root_dir, 'bau.html')
        with open(p, 'r', encoding='utf-8') as f:
            c = f.read()
        if 'gallery-grid' in c:
            c = re.sub(r'<div class="gallery-grid">.*?(?=</section>)', bau_snippet + '\n    ', c, flags=re.DOTALL)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(c)


print("⏳ 3/5 Fiksiram CMS Dashboard linkove (Mičem Django Admin)...")
cms_dash = os.path.join(BASE_DIR, 'templates/website/index.html')
with open(cms_dash, 'r', encoding='utf-8') as f:
    c = f.read()
# Mijenjamo rute iz Django Admina u naš Custom CMS
c = c.replace('/admin/website/galleryimage/', '{% url "website:cms_gallery" %}')
c = c.replace('/admin/website/videogallery/', '#" onclick="alert(\'Video Modul u pripremi\'); return false;')
c = c.replace('/admin/website/hitnaintervencija/', '#" onclick="alert(\'SOS Modul u pripremi\'); return false;')
c = c.replace('/admin/website/brand/', '#" onclick="alert(\'Brand Modul u pripremi\'); return false;')
with open(cms_dash, 'w', encoding='utf-8') as f:
    f.write(c)


print("⏳ 4/5 Postavljam Custom CMS rute i Backend logiku...")
urls_path = os.path.join(BASE_DIR, 'website/urls.py')
with open(urls_path, 'r', encoding='utf-8') as f:
    u = f.read()
if 'cms/gallery/' not in u:
    u = u.replace('urlpatterns = [', "urlpatterns = [\n    path('cms/gallery/', cms_views.cms_gallery, name='cms_gallery'),\n    path('cms/gallery/toggle/<int:id>/', cms_views.toggle_img, name='toggle_img'),\n")
    u = u.replace('from . import views', 'from . import views\nfrom . import cms_views')
    with open(urls_path, 'w', encoding='utf-8') as f:
        f.write(u)

cms_views_code = """from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import GalleryImage

@login_required
def cms_gallery(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['company_admin', 'superadmin'])):
        return redirect('homepage')
        
    if request.method == 'POST':
        image = request.FILES.get('image')
        category = request.POST.get('category', 'bau')
        caption_de = request.POST.get('caption_de', '')
        caption_hr = request.POST.get('caption_hr', '')
        if image:
            GalleryImage.objects.create(image=image, category=category, caption_de=caption_de, caption_hr=caption_hr, is_active=True, order=0)
            messages.success(request, 'Slika uspješno dodana!')
        return redirect('website:cms_gallery')

    images = GalleryImage.objects.all().order_by('-id')
    return render(request, 'website/cms/gallery_manager.html', {'images': images})

@login_required
def toggle_img(request, id):
    if request.method == 'POST':
        try:
            img = GalleryImage.objects.get(id=id)
            img.is_active = not img.is_active
            img.save()
            return JsonResponse({'ok': True, 'is_active': img.is_active})
        except:
            pass
    return JsonResponse({'ok': False})
"""
with open(os.path.join(BASE_DIR, 'website/cms_views.py'), 'w', encoding='utf-8') as f:
    f.write(cms_views_code)


print("⏳ 5/5 Kreiram Enterprise Formu za Galeriju (Višejezičnost + Tamna tema)...")
cms_dir = os.path.join(BASE_DIR, 'website/templates/website/cms')
os.makedirs(cms_dir, exist_ok=True)

gallery_html = """{% extends 'base.html' %}
{% block title %}Galerie Manager | Visković CMS{% endblock %}
{% block page_title %}Upravljanje Galerijom{% endblock %}
{% block content %}
<style>
    .cms-container { padding: 10px; color: var(--text); }
    .cms-header { border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 24px; display:flex; justify-content:space-between; align-items:center;}
    .cms-title { font-family: 'Barlow Condensed', sans-serif; font-size: 2rem; color: var(--gold); text-transform: uppercase; margin: 0; }
    
    .form-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 30px; }
    .form-label { color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; font-weight: 700; margin-bottom: 6px; display: block; }
    .custom-input { width: 100%; background: var(--black); border: 1px solid var(--border); color: var(--text); padding: 12px; border-radius: 8px; margin-bottom: 16px; }
    .custom-input:focus { border-color: var(--gold); outline: none; }
    
    .lang-badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 800; margin-right: 8px; }
    .bg-de { background: #3b82f6; color: white; }
    .bg-hr { background: #ef4444; color: white; }

    .submit-btn { background: var(--gold); color: #000; border: none; padding: 12px; border-radius: 8px; font-weight: 700; text-transform: uppercase; width: 100%; transition: 0.3s; }
    .submit-btn:hover { background: var(--gold-dim); }

    .table-custom { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--surface); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
    .table-custom th { background: var(--surface2); color: var(--text-dim); padding: 16px; text-align: left; font-size: 0.8rem; text-transform: uppercase; }
    .table-custom td { padding: 16px; border-top: 1px solid var(--border); vertical-align: middle; }
    .table-custom img { width: 60px; height: 60px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border); }
    
    .switch { position: relative; display: inline-block; width: 40px; height: 20px; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--surface2); border: 1px solid var(--border); border-radius: 20px; transition: .4s; }
    .slider:before { position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px; background-color: var(--text-dim); border-radius: 50%; transition: .4s; }
    input:checked + .slider { background-color: rgba(34, 197, 94, 0.2); border-color: #22c55e; }
    input:checked + .slider:before { transform: translateX(20px); background-color: #22c55e; }
    .status-active { color: #22c55e; font-weight: 700; font-size: 0.8rem; margin-left: 10px; }
    .status-inactive { color: var(--text-dim); font-weight: 700; font-size: 0.8rem; margin-left: 10px; }
</style>

<div class="cms-container">
    <div class="cms-header">
        <h1 class="cms-title"><i class="fas fa-images"></i> Enterprise Galerija</h1>
        <a href="{% url 'website:admin_panel' %}" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left"></i> Natrag na CMS Hub</a>
    </div>

    {% if messages %}{% for msg in messages %}<div style="background:rgba(34,197,94,0.1); border:1px solid #22c55e; color:#22c55e; padding:12px; border-radius:8px; margin-bottom:20px; font-weight:600;"><i class="fas fa-check-circle"></i> {{ msg }}</div>{% endfor %}{% endif %}

    <div class="row">
        <div class="col-lg-4">
            <div class="form-card">
                <h3 style="color:var(--text); font-size:1.1rem; margin-bottom:20px; font-weight:700; border-bottom:1px dashed var(--border); padding-bottom:10px;"><i class="fas fa-plus-circle text-warning"></i> Dodaj Referencu</h3>
                <form method="post" enctype="multipart/form-data" id="uploadForm">
                    {% csrf_token %}
                    <label class="form-label">Odaberi sliku *</label>
                    <input type="file" name="image" class="custom-input" required accept="image/*">
                    <label class="form-label">Kategorija</label>
                    <select name="category" class="custom-input">
                        <option value="bau">Visković BAU</option>
                        <option value="najam">VG Najam</option>
                    </select>
                    <div style="height:10px;"></div>
                    <label class="form-label"><span class="lang-badge bg-de">DE</span> Naslov (Njemački) *</label>
                    <input type="text" name="caption_de" class="custom-input" required placeholder="npr. Badezimmer Stuttgart">
                    <label class="form-label"><span class="lang-badge bg-hr">HR</span> Naslov (Hrvatski)</label>
                    <input type="text" name="caption_hr" class="custom-input" placeholder="npr. Kupaonica Stuttgart">
                    <button type="submit" class="submit-btn" id="submitBtn"><i class="fas fa-cloud-upload-alt"></i> Spremi i Objavi</button>
                </form>
            </div>
        </div>

        <div class="col-lg-8">
            <div style="overflow-x:auto;">
                <table class="table-custom">
                    <thead><tr><th width="80">Slika</th><th>Naslov</th><th>Kategorija</th><th class="text-center">Javno Vidljivo</th></tr></thead>
                    <tbody>
                        {% for img in images %}
                        <tr>
                            <td>{% if img.image %}<img src="{{ img.image.url }}">{% endif %}</td>
                            <td>
                                <div style="font-weight:700;">{{ img.caption_de|default:"-" }}</div>
                                <div style="font-size:0.8rem; color:var(--text-dim);">{{ img.caption_hr|default:"-" }}</div>
                            </td>
                            <td><span style="color:var(--gold);">{{ img.get_category_display|default:img.category|upper }}</span></td>
                            <td class="text-center">
                                <label class="switch">
                                    <input type="checkbox" onchange="toggleStatus(this, {{ img.id }})" {% if img.is_active %}checked{% endif %}>
                                    <span class="slider"></span>
                                </label>
                                <span class="{% if img.is_active %}status-active{% else %}status-inactive{% endif %}" id="status-text-{{ img.id }}">
                                    {% if img.is_active %}Aktivno{% else %}Skriveno{% endif %}
                                </span>
                            </td>
                        </tr>
                        {% empty %}
                        <tr><td colspan="4" class="text-center" style="padding:40px; color:var(--text-dim);">Baza je prazna.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
    document.getElementById('uploadForm').addEventListener('submit', function() {
        document.getElementById('submitBtn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Zapisivanje...';
    });
    function toggleStatus(checkbox, imgId) {
        const textSpan = document.getElementById('status-text-' + imgId);
        textSpan.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        checkbox.disabled = true;
        const fd = new FormData(); fd.append('csrfmiddlewaretoken', '{{ csrf_token }}');
        fetch(`/website/cms/gallery/toggle/${imgId}/`, { method: 'POST', body: fd })
        .then(r => r.json()).then(d => {
            checkbox.disabled = false;
            if(d.ok) {
                textSpan.innerHTML = d.is_active ? 'Aktivno' : 'Skriveno';
                textSpan.className = d.is_active ? 'status-active' : 'status-inactive';
            }
        });
    }
</script>
{% endblock %}"""
with open(os.path.join(cms_dir, 'gallery_manager.html'), 'w', encoding='utf-8') as f:
    f.write(gallery_html)

os.system("chown -R www-data:www-data /var/www/fina-connect/")
os.system("supervisorctl restart fina-connect")

print("✅ ENTERPRISE ARHITEKTURA JE 100% POSTAVLJENA! Osvježite stranice.")
