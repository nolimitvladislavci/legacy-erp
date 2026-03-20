import os
import re

VIEWS_FILE = '/var/www/fina-connect/website/views.py'
BAU_HTML = '/var/www/fina-connect/website/templates/website/bau.html'

print("⏳ 1/2 Oživljavam Backend Logiku za Medije...")
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_code = f.read()

# Zamjena stare funkcije sa pametnom funkcijom koja skuplja i slike i videe
old_view_pattern = re.compile(r'def bau_page\(request\):.*?return render\(request, \'website/bau\.html\'.*?\)', re.DOTALL)

new_view = """def bau_page(request):
    \"\"\"Landing stranica za građevinu i sanacije s pametnom galerijom\"\"\"
    media_items = []
    try:
        from website.models import GalleryImage, VideoGallery
        
        # 1. Prikupi Slike
        slike = GalleryImage.objects.filter(is_active=True)
        # Ako imamo slike u kategoriji 'bau', uzmi samo njih, inače uzmi sve
        if slike.filter(category='bau').exists():
            slike = slike.filter(category='bau')
            
        for s in slike.order_by('-id')[:8]:
            # Refleksija: Tražimo kako se polje točno zove (image, slika, file...)
            url_obj = getattr(s, 'image', getattr(s, 'slika', getattr(s, 'file', None)))
            if url_obj and hasattr(url_obj, 'url'):
                title = getattr(s, 'title', getattr(s, 'naslov', 'Badsanierung Referenz'))
                media_items.append({'type': 'image', 'url': url_obj.url, 'title': title})
                
        # 2. Prikupi Videe
        videi = VideoGallery.objects.filter(is_active=True)
        if videi.filter(kategorija='bau').exists():
            videi = videi.filter(kategorija='bau')
            
        for v in videi.order_by('-id')[:4]:
            v_file = getattr(v, 'video_file', getattr(v, 'file', getattr(v, 'video', None)))
            v_url = getattr(v, 'embed_url', getattr(v, 'url', getattr(v, 'youtube_url', None)))
            title = getattr(v, 'title', getattr(v, 'naslov', 'Video Referenz'))
            
            if v_file and hasattr(v_file, 'url'):
                media_items.append({'type': 'video_file', 'url': v_file.url, 'title': title})
            elif v_url:
                media_items.append({'type': 'video_embed', 'url': v_url, 'title': title})
                
    except Exception as e:
        print(f"Greška pri učitavanju medija: {e}")
        
    return render(request, 'website/bau.html', {'media_items': media_items})"""

if old_view_pattern.search(views_code):
    views_code = old_view_pattern.sub(new_view, views_code)
else:
    # Ako regex ne prođe (zaštita), dodajemo na kraj
    views_code += "\n\n" + new_view

with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(views_code)


print("⏳ 2/2 Ažuriram Dizajn Galerije (Slike + MP4)...")
with open(BAU_HTML, 'r', encoding='utf-8') as f:
    html = f.read()

# Zamjena HTML bloka galerije
stari_grid_pattern = re.compile(r'<div class="gallery-grid">.*?</div>\n</section>', re.DOTALL)

novi_grid = """<div class="gallery-grid">
        {% if media_items %}
            {% for item in media_items %}
            <div class="gallery-item">
                {% if item.type == 'image' %}
                    <img src="{{ item.url }}" alt="{{ item.title }}">
                {% elif item.type == 'video_file' %}
                    <video width="100%" height="100%" style="object-fit: cover; background: #000;" controls muted playsinline preload="metadata">
                        <source src="{{ item.url }}" type="video/mp4">
                        Ihr Browser unterstützt keine Videos.
                    </video>
                {% elif item.type == 'video_embed' %}
                    <iframe src="{{ item.url }}" width="100%" height="100%" style="border:none;" allowfullscreen></iframe>
                {% endif %}
                
                <div class="gallery-overlay" style="pointer-events: none;">
                    <div class="gallery-title">{{ item.title }}</div>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="gallery-item" style="display: flex; align-items: center; justify-content: center; color: var(--text-dim);">
                <div style="text-align:center"><i class="fas fa-camera fa-3x" style="opacity:0.2; margin-bottom:16px"></i><br><span style="font-family:'Barlow Condensed',sans-serif; letter-spacing:2px; text-transform:uppercase;">Badezimmer Stuttgart</span></div>
            </div>
            <div class="gallery-item" style="display: flex; align-items: center; justify-content: center; color: var(--text-dim);">
                <div style="text-align:center"><i class="fas fa-video fa-3x" style="opacity:0.2; margin-bottom:16px"></i><br><span style="font-family:'Barlow Condensed',sans-serif; letter-spacing:2px; text-transform:uppercase;">Innenausbau Ludwigsburg</span></div>
            </div>
        {% endif %}
    </div>
</section>"""

if stari_grid_pattern.search(html):
    html = stari_grid_pattern.sub(novi_grid, html)

with open(BAU_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

os.system("supervisorctl restart fina-connect")
print("✅ GALERIJA JE USPJEŠNO OŽIVLJENA!")
