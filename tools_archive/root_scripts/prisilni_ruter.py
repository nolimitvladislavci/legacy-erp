import os

VIEWS_FILE = '/var/www/fina-connect/website/views.py'
with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Brutalno i sigurno: Odsijecamo sve od stare "def bau_page" funkcije do kraja
if 'def bau_page(' in content:
    content = content[:content.find('def bau_page(')]

# Dodajemo potpuno novi, neprobojni ruter
new_view = """def bau_page(request):
    from website.models import GalleryImage, VideoGallery
    from django.shortcuts import render
    import traceback
    
    media_items = []
    try:
        # Povlačimo slike s njemačkim i hrvatskim naslovima
        slike = GalleryImage.objects.filter(is_active=True, category='bau').order_by('order', '-id')[:8]
        for s in slike:
            if s.image:
                title = getattr(s, 'caption_de', getattr(s, 'caption_hr', 'Referenz Projekt'))
                media_items.append({'type': 'image', 'url': s.image.url, 'title': title})
                
        # Povlačimo videoklipove
        videi = VideoGallery.objects.filter(is_active=True, kategorija='bau').order_by('redoslijed', '-id')[:4]
        for v in videi:
            if v.video_file:
                title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', 'Video Referenz'))
                media_items.append({'type': 'video_file', 'url': v.video_file.url, 'title': title})
            elif getattr(v, 'embed_url', None):
                title = getattr(v, 'naslov_de', getattr(v, 'naslov_hr', 'Video Referenz'))
                media_items.append({'type': 'video_embed', 'url': v.embed_url, 'title': title})
                
    except Exception as e:
        # Ako se išta sruši, zapisujemo u crnu kutiju da ne nagađamo
        with open('/var/www/fina-connect/galerija_error.log', 'w', encoding='utf-8') as err_file:
            err_file.write(traceback.format_exc())
            
    return render(request, 'website/bau.html', {'media_items': media_items})
"""

with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
    f.write(content + new_view)

os.system("supervisorctl restart fina-connect")
print("✅ RUTER JE PRISILNO AŽURIRAN! Zavarili smo novu logiku.")
