import os
import re

VIEWS_FILE = '/var/www/fina-connect/website/views.py'

print("⏳ Otključavam filtere u bazi za prikaz slika...")
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_code = f.read()

# Potpuno otporna funkcija koja ignorira stroge filtere kategorija
old_view_pattern = re.compile(r'def bau_page\(request\):.*?return render\(request, \'website/bau\.html\', \{.*?\}\)', re.DOTALL)

new_view = """def bau_page(request):
    \"\"\"Landing stranica za građevinu i sanacije s pametnom galerijom\"\"\"
    media_items = []
    try:
        from website.models import GalleryImage, VideoGallery
        
        # 1. Uzimamo sve slike (bez strogog filtera koji bi mogao srušiti upit)
        slike = GalleryImage.objects.all().order_by('-id')[:8]
        for s in slike:
            # Tražimo pravo polje za sliku
            url_obj = getattr(s, 'image', getattr(s, 'slika', getattr(s, 'file', None)))
            if url_obj and hasattr(url_obj, 'url'):
                title = getattr(s, 'title', getattr(s, 'naslov', 'Referenz Projekt'))
                media_items.append({'type': 'image', 'url': url_obj.url, 'title': title})
                
        # 2. Uzimamo sve videe
        videi = VideoGallery.objects.all().order_by('-id')[:4]
        for v in videi:
            v_file = getattr(v, 'video_file', getattr(v, 'file', getattr(v, 'video', None)))
            v_url = getattr(v, 'embed_url', getattr(v, 'url', getattr(v, 'youtube_url', None)))
            title = getattr(v, 'title', getattr(v, 'naslov', 'Video Referenz'))
            
            if v_file and hasattr(v_file, 'url'):
                media_items.append({'type': 'video_file', 'url': v_file.url, 'title': title})
            elif v_url:
                media_items.append({'type': 'video_embed', 'url': v_url, 'title': title})
                
    except Exception as e:
        print(f"Galerija Greška: {e}")
        
    return render(request, 'website/bau.html', {'media_items': media_items})"""

if old_view_pattern.search(views_code):
    views_code = old_view_pattern.sub(new_view, views_code)
    with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
        f.write(views_code)
    
os.system("supervisorctl restart fina-connect")
print("✅ GALERIJA JE OTKLJUČANA! Osvježite stranicu.")
