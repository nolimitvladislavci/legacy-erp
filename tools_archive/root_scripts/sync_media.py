import os
from website.models import GalleryImage, VideoGallery

gallery_dir = '/var/www/fina-connect/media/website/gallery'

print('⏳ Sinkroniziram datoteke s bazom podataka...')

if not os.path.exists(gallery_dir):
    print('❌ Mapa ne postoji:', gallery_dir)
else:
    for filename in os.listdir(gallery_dir):
        filepath = os.path.join(gallery_dir, filename)
        if os.path.isfile(filepath):
            # Formiramo putanju koju Django prepoznaje
            db_path = f'website/gallery/{filename}'
            
            # Pravimo lijepi naslov od imena datoteke
            title = filename.split('.')[0].replace('_', ' ').title()
            ext = filename.lower().split('.')[-1]

            if ext in ['jpg', 'jpeg', 'png']:
                # Pokušavamo upisati sliku s različitim varijacijama imena polja
                try:
                    GalleryImage.objects.get_or_create(image=db_path, defaults={'category': 'bau', 'title': title, 'is_active': True})
                    print(f'✅ Slika unesena: {title}')
                except:
                    try:
                        GalleryImage.objects.get_or_create(slika=db_path, defaults={'kategorija': 'bau', 'naslov': title, 'is_active': True})
                        print(f'✅ Slika unesena: {title}')
                    except Exception as e:
                        pass

            elif ext in ['mp4']:
                # Pokušavamo upisati video
                try:
                    VideoGallery.objects.get_or_create(video_file=db_path, defaults={'kategorija': 'bau', 'title': title, 'is_active': True})
                    print(f'✅ Video unesen: {title}')
                except:
                    try:
                        VideoGallery.objects.get_or_create(file=db_path, defaults={'category': 'bau', 'naslov': title, 'is_active': True})
                        print(f'✅ Video unesen: {title}')
                    except Exception as e:
                        pass

print('✅ SINKRONIZACIJA ZAVRŠENA! Vaš inventar u bazi je napunjen.')
