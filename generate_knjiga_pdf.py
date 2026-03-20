#!/usr/bin/env python3
"""Generate Knjiga Boljitaka PDF report"""
import json
import os
import sys

sys.path.insert(0, "/var/www/fina-connect")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle

GOLD = HexColor("#c9a84c")
DARK = HexColor("#0a0a0a")
DARK_GRAY = HexColor("#1a1a1a")
LIGHT_GRAY = HexColor("#2a2a2a")
TEXT_WHITE = HexColor("#f0f0f0")
TEXT_GRAY = HexColor("#999999")
GREEN = HexColor("#22c55e")
RED = HexColor("#ef4444")
ORANGE = HexColor("#f59e0b")

OUTPUT = "/var/www/fina-connect/knjiga_boljitaka.pdf"

# Load test results
with open("/var/www/fina-connect/knjiga_boljitaka.json") as f:
    data = json.load(f)

c = canvas.Canvas(OUTPUT, pagesize=A4)
w, h = A4
margin = 20 * mm
usable_w = w - 2 * margin

def draw_header(c, y):
    # Black background header
    c.setFillColor(DARK)
    c.rect(0, y - 5*mm, w, 45*mm, fill=1, stroke=0)

    # Gold accent line
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(margin, y - 3*mm, w - margin, y - 3*mm)

    # Title
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(margin, y + 22*mm, "LIMIT CONNECT")

    c.setFillColor(TEXT_WHITE)
    c.setFont("Helvetica", 14)
    c.drawString(margin, y + 12*mm, "Knjiga Boljitaka — Izvještaj o kvaliteti sustava")

    c.setFillColor(TEXT_GRAY)
    c.setFont("Helvetica", 10)
    c.drawString(margin, y + 3*mm, f"Datum: {data['timestamp']}  |  Server: 85.9.201.204  |  Domena: limit-connect.com")

    # Bottom gold line
    c.line(margin, y - 3*mm, w - margin, y - 3*mm)

    return y - 10*mm

def draw_summary_box(c, y):
    box_h = 30*mm
    y_top = y

    # Background
    c.setFillColor(DARK)
    c.rect(margin, y - box_h, usable_w, box_h, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.rect(margin, y - box_h, usable_w, box_h, fill=0, stroke=1)

    # Stats
    passed = data["passed"]
    failed = data["failed"]
    errors = data["errors"]
    total = data["total"]
    pct = int(passed / total * 100) if total else 0

    col_w = usable_w / 4
    stats = [
        (f"{passed}/{total}", "PROŠLO", GREEN),
        (f"{failed}", "PALO", RED if failed > 0 else GREEN),
        (f"{errors}", "GREŠKA", ORANGE if errors > 0 else GREEN),
        (f"{pct}%", "OCJENA", GOLD),
    ]

    for i, (val, label, color) in enumerate(stats):
        cx = margin + col_w * i + col_w / 2
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(cx, y - 14*mm, val)
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 9)
        c.drawCentredString(cx, y - 22*mm, label)

    return y - box_h - 8*mm

def draw_section(c, y, section_num, title, tests):
    # Section header
    if y < 60*mm:
        c.showPage()
        y = h - margin

    c.setFillColor(DARK)
    c.rect(margin, y - 8*mm, usable_w, 8*mm, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.5)
    c.line(margin, y - 8*mm, margin + usable_w, y - 8*mm)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin + 3*mm, y - 6*mm, f"[{section_num}] {title}")

    y -= 12*mm

    for t in tests:
        if y < 25*mm:
            c.showPage()
            y = h - margin

        status = t["status"]
        if status == "PASS":
            icon = "✓"
            color = GREEN
        elif status == "FAIL":
            icon = "✗"
            color = RED
        else:
            icon = "!"
            color = ORANGE

        # Status icon
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin + 2*mm, y, icon)

        # Test name
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin + 10*mm, y, t["name"])

        # Detail
        c.setFillColor(TEXT_GRAY if status == "PASS" else color)
        c.setFont("Helvetica", 8)
        detail = t["detail"][:85]
        c.drawString(margin + 10*mm, y - 4*mm, detail)

        y -= 12*mm

    return y

def draw_improvements_log(c, y):
    if y < 100*mm:
        c.showPage()
        y = h - margin

    c.setFillColor(DARK)
    c.rect(margin, y - 8*mm, usable_w, 8*mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin + 3*mm, y - 6*mm, "PROVEDENE POPRAVKE — 2026-03-12")
    c.setStrokeColor(GOLD)
    c.line(margin, y - 8*mm, margin + usable_w, y - 8*mm)

    y -= 16*mm

    improvements = [
        ("KRITIČNO", "IMAP BODY.PEEK[]", "Email se više ne označava kao pročitan prije obrade. Sprečava gubitak računa ako AI parsiranje ili DB upis padne.", "Implementirano"),
        ("KRITIČNO", "Explicit \\Seen flag", "Email se eksplicitno označava kao pročitan TEK nakon što su svi privitci uspješno spremljeni u bazu.", "Implementirano"),
        ("KRITIČNO", "FailedImport model", "Svaki preskočeni privitak (DB greška, format error) se logira u posebnu tablicu. Knjigovođa može vidjeti što je propušteno.", "Implementirano"),
        ("VISOKO", "Stale batch detekcija", "Celery task svakih 10 min provjerava batcheve zaglavljene u 'pending' >30 min. Automatski ih označava kao error s upozorenjem.", "Implementirano"),
        ("VISOKO", "Konto balance validation", "clean() metoda na JournalEntry — nebalansirana temeljnica (duguje ≠ potražuje) baca ValidationError.", "Implementirano"),
        ("VISOKO", "Unique entry_number", "DB constraint unique_together(company, entry_number) — sprečava duplikate temeljnica unutar iste firme.", "Implementirano"),
        ("SREDNJE", "Domena limit-connect.com", "Puni rebrand: FINA-Connect → LIMIT Connect. 178 fajlova ažurirano. SSL, nginx, Django settings.", "Implementirano"),
        ("SREDNJE", "Knjiga Boljitaka", "26 automatiziranih testova pokriva: Celery, Redis, IMAP, Konto, DB, Email, Server, SSL, Domena.", "Implementirano"),
    ]

    priorities = {"KRITIČNO": RED, "VISOKO": ORANGE, "SREDNJE": GOLD}

    for priority, title, desc, status in improvements:
        if y < 30*mm:
            c.showPage()
            y = h - margin

        # Priority badge
        badge_color = priorities.get(priority, GOLD)
        c.setFillColor(badge_color)
        c.setFont("Helvetica-Bold", 7)
        badge_w = c.stringWidth(priority, "Helvetica-Bold", 7) + 4*mm
        c.roundRect(margin, y - 1*mm, badge_w, 5*mm, 1.5*mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.drawString(margin + 2*mm, y, priority)

        # Title
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin + badge_w + 3*mm, y, title)

        # Status badge
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 7)
        status_w = c.stringWidth(status, "Helvetica-Bold", 7) + 4*mm
        c.roundRect(w - margin - status_w, y - 1*mm, status_w, 5*mm, 1.5*mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.drawString(w - margin - status_w + 2*mm, y, status)

        # Description
        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 7.5)
        # Word wrap
        words = desc.split()
        line = ""
        line_y = y - 6*mm
        for word in words:
            test_line = line + " " + word if line else word
            if c.stringWidth(test_line, "Helvetica", 7.5) > usable_w - 5*mm:
                c.drawString(margin + 2*mm, line_y, line)
                line = word
                line_y -= 4*mm
            else:
                line = test_line
        if line:
            c.drawString(margin + 2*mm, line_y, line)

        y = line_y - 8*mm

    return y

def draw_gemini_response(c, y):
    if y < 80*mm:
        c.showPage()
        y = h - margin

    c.setFillColor(DARK)
    c.rect(margin, y - 8*mm, usable_w, 8*mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin + 3*mm, y - 6*mm, "ODGOVOR NA GEMINI ANALIZU")
    c.setStrokeColor(GOLD)
    c.line(margin, y - 8*mm, margin + usable_w, y - 8*mm)
    y -= 16*mm

    responses = [
        ("Gemini tvrdnja #1:", "CELERY_TASK_ACKS_LATE nedostaje",
         "NETOČNO — postavka je bila aktivna (True) prije Gemini analize. Gemini nije pregledao aktualni settings.py.",
         "Netočno"),
        ("Gemini tvrdnja #2:", "IMAP Seen flag problem",
         "DJELOMIČNO TOČNO — FETCH RFC822 je automatski postavljao Seen flag. Popravljeno: sada koristi BODY.PEEK[] + explicit Seen nakon obrade.",
         "Popravljeno"),
        ("Gemini tvrdnja #3:", "Konto nema balance enforcement",
         "TOČNO — is_balanced() je bio samo @property bez clean() metode. Dodana clean() validacija + unique_together constraint.",
         "Popravljeno"),
    ]

    colors = {"Netočno": RED, "Popravljeno": GREEN, "Djelomično": ORANGE}

    for title, claim, response, verdict in responses:
        if y < 35*mm:
            c.showPage()
            y = h - margin

        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, y, title)
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(margin + c.stringWidth(title, "Helvetica-Bold", 9) + 2*mm, y, f'"{claim}"')

        verdict_color = colors.get(verdict, GOLD)
        c.setFillColor(verdict_color)
        c.setFont("Helvetica-Bold", 7)
        vw = c.stringWidth(verdict, "Helvetica-Bold", 7) + 4*mm
        c.roundRect(w - margin - vw, y - 1*mm, vw, 5*mm, 1.5*mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.drawString(w - margin - vw + 2*mm, y, verdict)

        c.setFillColor(TEXT_GRAY)
        c.setFont("Helvetica", 7.5)
        words = response.split()
        line = ""
        line_y = y - 6*mm
        for word in words:
            test_line = line + " " + word if line else word
            if c.stringWidth(test_line, "Helvetica", 7.5) > usable_w - 5*mm:
                c.drawString(margin + 2*mm, line_y, line)
                line = word
                line_y -= 4*mm
            else:
                line = test_line
        if line:
            c.drawString(margin + 2*mm, line_y, line)

        y = line_y - 10*mm

    return y

def draw_footer(c):
    c.setFillColor(DARK)
    c.rect(0, 0, w, 12*mm, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.line(margin, 12*mm, w - margin, 12*mm)
    c.setFillColor(TEXT_GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(margin, 5*mm, f"LIMIT CONNECT © 2026  |  Generirano: {data['timestamp']}  |  Povjerljiv dokument")
    c.drawRightString(w - margin, 5*mm, "Knjiga Boljitaka v1.0")

# ══════════════════════════════════════════════
# BUILD PDF
# ══════════════════════════════════════════════

y = h - margin

# Page 1: Header + Summary + Test Results
y = draw_header(c, y - 5*mm)
y -= 5*mm
y = draw_summary_box(c, y)

# Group tests by category
categories = {}
for t in data["tests"]:
    cat = t["category"]
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(t)

section_titles = {
    "Celery": "CELERY SIGURNOST",
    "Redis": "REDIS KONEKCIJA",
    "IMAP": "IMAP SIGURNOST",
    "Konto": "KONTO / KNJIGOVODSTVO",
    "Import": "IMPORT BATCH STANJE",
    "Domena": "DOMENA I BRANDING",
    "DB": "BAZA PODATAKA",
    "Email": "EMAIL RAMPA",
    "Server": "SERVER RESURSI",
    "SSL": "SSL CERTIFIKATI",
}

for i, (cat, tests) in enumerate(categories.items(), 1):
    title = section_titles.get(cat, cat.upper())
    y = draw_section(c, y, i, title, tests)

draw_footer(c)

# Page 2+: Improvements log
c.showPage()
y = h - margin
y = draw_improvements_log(c, y)
y = draw_gemini_response(c, y)
draw_footer(c)

c.save()
print(f"PDF generiran: {OUTPUT}")
