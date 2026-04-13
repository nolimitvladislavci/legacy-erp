#!/usr/bin/env python3
"""
Generira QR kod PNG za svaki TableQR Široki Šor.
Output: media/gastro/table_qr/
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

import qrcode
from PIL import Image, ImageDraw, ImageFont
from gastro_menu.models import TableQR, DigitalMenu
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

DOMAIN = 'https://limit-connect.com'
OUTPUT_DIR = '/var/www/fina-connect/media/gastro/table_qr'
os.makedirs(OUTPUT_DIR, exist_ok=True)

menu = DigitalMenu.objects.get(slug='korpas-doo-siroki-sor')
tables = TableQR.objects.filter(menu=menu).order_by('table_zone', 'table_number')

for tqr in tables:
    url = f'{DOMAIN}/gastro-menu/menu/{menu.slug}/?table={tqr.table_number.replace(" ", "+")}'

    qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=12, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#1a0a06', back_color='white').convert('RGB')

    qr_w, qr_h = img.size
    canvas = Image.new('RGB', (qr_w, qr_h + 70), 'white')
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
        font_sm = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font

    label = tqr.table_number
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((qr_w - text_w) / 2, qr_h + 5), label, fill='#1a0a06', font=font)

    sub = 'Skeniraj za jelovnik'
    bbox2 = draw.textbbox((0, 0), sub, font=font_sm)
    sub_w = bbox2[2] - bbox2[0]
    draw.text(((qr_w - sub_w) / 2, qr_h + 42), sub, fill='#666', font=font_sm)

    filename = f'qr_{tqr.table_number.replace(" ", "_").lower()}.png'
    filepath = os.path.join(OUTPUT_DIR, filename)
    canvas.save(filepath)

    tqr.qr_image = f'gastro/table_qr/{filename}'
    tqr.save(update_fields=['qr_image'])

    print(f'  {tqr.table_number:15s} -> {filename}')

print(f'\n{tables.count()} QR kodova -> {OUTPUT_DIR}')
