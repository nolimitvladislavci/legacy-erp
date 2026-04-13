#!/usr/bin/env python3
"""
Generira A4 PDF sa QR kodovima za stolove (4 po stranici).
Output: media/gastro/siroki_sor_qr_print.pdf
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rc
from reportlab.lib.units import cm
from gastro_menu.models import TableQR, DigitalMenu
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

menu = DigitalMenu.objects.get(slug='korpas-doo-siroki-sor')
tables = list(TableQR.objects.filter(menu=menu).order_by('table_zone', 'table_number'))

OUTPUT = '/var/www/fina-connect/media/gastro/siroki_sor_qr_print.pdf'
QR_DIR = '/var/www/fina-connect/media/gastro/table_qr'

c = rc.Canvas(OUTPUT, pagesize=A4)
w, h = A4

positions = [
    (1.5*cm, h - 14*cm),
    (11*cm, h - 14*cm),
    (1.5*cm, h - 27.5*cm),
    (11*cm, h - 27.5*cm),
]

for i, tqr in enumerate(tables):
    pos_idx = i % 4
    if pos_idx == 0 and i > 0:
        c.showPage()

    x, y = positions[pos_idx]
    qr_file = os.path.join(QR_DIR, f'qr_{tqr.table_number.replace(" ", "_").lower()}.png')

    if os.path.exists(qr_file):
        c.drawImage(qr_file, x, y, width=8*cm, height=9*cm, preserveAspectRatio=True)

    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(x + 4*cm, y - 0.8*cm, tqr.table_number)

    c.setFont('Helvetica', 10)
    c.drawCentredString(x + 4*cm, y - 1.6*cm, 'Skeniraj za jelovnik')

    c.setFont('Helvetica', 7)
    c.drawCentredString(x + 4*cm, y - 2.3*cm, 'Sirok Sor — Izletiste Kusaonica | Vladislavci')

c.save()
pages = (len(tables) + 3) // 4
print(f'PDF: {OUTPUT}')
print(f'{len(tables)} QR kodova, {pages} stranica')
