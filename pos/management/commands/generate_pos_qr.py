"""
Management command: generate_pos_qr
Generates QR codes and print-ready PDFs for POS terminals.

Usage:
    python manage.py generate_pos_qr --company "UVIJEK FRIŠKO"
    python manage.py generate_pos_qr  # all terminals
"""
import os
import io

from django.core.management.base import BaseCommand
from django.conf import settings

from pos.models import POSTerminal


class Command(BaseCommand):
    help = "Generate QR codes and print PDFs for POS terminal instant-open"

    def add_arguments(self, parser):
        parser.add_argument("--company", type=str, default="", help="Filter by company name (contains)")

    def handle(self, *args, **options):
        import qrcode
        from reportlab.lib.pagesizes import A6
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.utils import ImageReader

        company_filter = options["company"]
        qs = POSTerminal.objects.filter(is_active=True).select_related("company")
        if company_filter:
            qs = qs.filter(company__name__icontains=company_filter)

        if not qs.exists():
            self.stderr.write(self.style.ERROR("No terminals found."))
            return

        base_url = "https://limit-connect.com"
        media_root = settings.MEDIA_ROOT

        for terminal in qs:
            # Ensure token exists
            if not terminal.access_token:
                terminal.save()  # save() auto-generates token

            url = f"{base_url}/pos/qr/{terminal.access_token}/"

            # Create output directory
            company_slug = terminal.company.name.replace(" ", "_")[:30]
            out_dir = os.path.join(media_root, "pos_qr", company_slug)
            os.makedirs(out_dir, exist_ok=True)

            terminal_slug = terminal.name.lower().replace(" ", "_").replace("/", "-")[:30]

            # Generate QR code PNG
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            png_path = os.path.join(out_dir, f"{terminal_slug}.png")
            qr_img.save(png_path)

            # Generate print-ready PDF (A6)
            pdf_path = os.path.join(out_dir, f"{terminal_slug}_print.pdf")
            c = pdf_canvas.Canvas(pdf_path, pagesize=A6)
            w, h = A6

            # Company name
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(w / 2, h - 1.5 * cm, terminal.company.name)

            # Terminal name
            c.setFont("Helvetica", 11)
            c.drawCentredString(w / 2, h - 2.3 * cm, terminal.name)

            # QR code image (centered, 8x8 cm)
            qr_buf = io.BytesIO()
            qr_img.save(qr_buf, format="PNG")
            qr_buf.seek(0)
            qr_size = 7 * cm
            x_qr = (w - qr_size) / 2
            y_qr = (h - qr_size) / 2 - 0.5 * cm
            c.drawImage(ImageReader(qr_buf), x_qr, y_qr, qr_size, qr_size)

            # Instruction text
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(w / 2, y_qr - 0.6 * cm, "Skeniraj za otvaranje blagajne")

            # Footer
            c.setFont("Helvetica", 8)
            c.drawCentredString(w / 2, 0.8 * cm, "limit-connect.com")

            c.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Terminal: {terminal.name}\n"
                    f"  URL: {url}\n"
                    f"  QR:  {png_path}\n"
                    f"  PDF: {pdf_path}\n"
                )
            )

        self.stdout.write(self.style.SUCCESS("Done."))
