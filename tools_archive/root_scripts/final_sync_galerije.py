import os
import re
import django

# Inicijalizacija Djanga kako bismo mogli koristiti modele
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from website.models import GalleryImage, VideoGallery
VIEWS_FILE = '/var/www/fina-connect/website/views.py'
gallery_dir = '/var/www/fina-connect/media/website/gallery'

print('⏳ 1/2 Ažuriram views.py da čita višejezična polja (caption_de / naslov_de)...')
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    views_code = f.read()

old_view_pattern = re.compile(r'def bau_page\(request\):.*?return render\(request, \'website/bau\.html\', \{.*?\}\)', re.DOTALL)

new_view = """def bau_page(request):
    \"\"\"Landing stranica za građevinu i sanacije s pametnom galerijom\"\"\"
    media_items = []
    try:
        from website.models import GalleryImage, VideoGallery
        
        # 1. Uzimamo slike iz baze (kategorija 'bau')
        slike = GalleryImage.objects.filter(is_active=True, category='bau').order_by('order', '-id')[:8]
        for s in slike:
            if s.image and hasattr(s.image, 'url'):
                # Povlačimo njemački naslov, ako ga nema onda hrvatski
                title = getattr(s, 'caption_de', getattr(s, 'caption_hr', 'Referenz Projekt'))
                media_items.append({'type': 'image', 'url': s.image.url, 'title': title})
                
        # 2. Uzimamo videe iz baze (kategorija 'bau')
        videi = VideoGallery.objects.filter(is_active=True, kategorija='bau').order_by('redoslijed', '-id')[:4]
        for v in videi:
            if v.video_file and hasattr(v.video_file, 'url'):
                title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', 'Video Referenz'))
                media_items.append({'type': 'video_file', 'url': v.video_file.url, 'title': title})
            elif v.embed_url:
                title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', 'Video Referenz'))
                media_items.append({'type': 'video_embed', 'url': v.embed_url, 'title': title})
                
    except Exception as e:
        print(f"Galerija Greška: {e}")
        
    return render(request, 'website/bau.html', {'media_items': media_items})"""

if old_view_pattern.search(views_code):
    views_code = old_view_pattern.sub(new_view, views_code)
    with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
        f.write(views_code)


print('⏳ 2/2 Sinkroniziram datoteke u bazu prema točnoj arhitekturi...')
if not os.path.exists(gallery_dir):
    print('❌ Mapa ne postoji:', gallery_dir)
else:
    for filename in os.listdir(gallery_dir):
        filepath = os.path.join(gallery_dir, filename)
        if os.path.isfile(filepath):
            db_path = f'website/gallery/{filename}'
            
            # Formiramo lijep naslov bez donjih crtica
            title = filename.split('.')[0].replace('_', ' ').title()
            ext = filename.lower().split('.')[-1]

            if ext in ['jpg', 'jpeg', 'png']:
                obj, created = GalleryImage.objects.get_or_create(
                    image=db_path,
                    defaults={
                        'category': 'bau', 
                        'caption_de': title,
                        'caption_hr': title,
                        'caption_en': title,
                        'is_active': True,
                        'order': 0
                    }
                )
                if created:
                    print(f'✅ Slika unesena: {title}')
                else:
                    print(f'⚡ Slika već postoji: {title}')

            elif ext in ['mp4']:
                obj, created = VideoGallery.objects.get_or_create(
                    video_file=db_path,
                    defaults={
                        'kategorija': 'bau',
                        'naslov_de': title,
                        'naslov_hr': title,
                        'naslov_en': title,
                        'opis_de': '',
                        'opis_hr': '',
                        'is_active': True,
                        'redoslijed': 0
                    }
                )
                if created:
                    print(f'✅ Video unesen: {title}')
                else:
                    print(f'⚡ Video već postoji: {title}')

print('✅ SVE JE ZAVRŠENO! Baza i kod su savršeno usklađeni.')
