"""
LIMIT e-Knjiznica — Source Connectors.

Povezuje vanjske besplatne izvore knjiga u jedinstven katalog:
- Project Gutenberg (60.000+ javna domena)
- OpenLibrary (metadata + covers)
- Google Books (fallback metadata)
- BEK / elektronickeknjige.com (384 HR naslova)
- eLektire / lektire.skole.hr (310+ HR lektira)
- Wikizvor / hr.wikisource.org (5.000+ HR tekstova)
- Internet Archive (CDL posudba)
"""
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from core.company_utils import get_user_company
from .models import Book, Author, BookCopy, Category


SOURCES = {
    "gutenberg": {
        "name": "Project Gutenberg",
        "url": "https://www.gutenberg.org",
        "description": "60.000+ knjiga u javnoj domeni. Besplatno.",
        "icon": "bi-globe",
        "color": "#22c55e",
        "legal": "Javna domena (70+ godina od smrti autora)",
        "formats": ["EPUB", "PDF", "HTML", "Plain Text"],
        "api": "https://gutendex.com/books/",
    },
    "openlibrary": {
        "name": "Open Library",
        "url": "https://openlibrary.org",
        "description": "Metadata + naslovnice za 20M+ knjiga.",
        "icon": "bi-book",
        "color": "#3b82f6",
        "legal": "Otvoreni podaci (metapodaci slobodni)",
        "formats": ["Metadata", "Covers"],
        "api": "https://openlibrary.org/search.json",
    },
    "bek": {
        "name": "BEK — Besplatne elektronicke knjige",
        "url": "https://elektronickeknjige.com/bek/",
        "description": "384 naslova hrvatske knjizevnosti. Bez registracije.",
        "icon": "bi-flag",
        "color": "#ef4444",
        "legal": "Besplatno uz dozvolu autora",
        "formats": ["PDF", "EPUB"],
    },
    "elektire": {
        "name": "eLektire (CARNET)",
        "url": "https://lektire.skole.hr/",
        "description": "310+ lektira za OS i SS. Zahtijeva AAI@EduHr.",
        "icon": "bi-mortarboard",
        "color": "#f59e0b",
        "legal": "Besplatno za ucenike/studente",
        "formats": ["Online citac"],
    },
    "wikizvor": {
        "name": "Wikizvor (Wikisource HR)",
        "url": "https://hr.wikisource.org/",
        "description": "5.000+ tekstova hrvatske i svjetske knjizevnosti.",
        "icon": "bi-wikipedia",
        "color": "#8b5cf6",
        "legal": "Javna domena / CC licenca",
        "formats": ["HTML", "PDF export"],
    },
    "archive": {
        "name": "Internet Archive",
        "url": "https://archive.org/details/texts",
        "description": "Milijuni knjiga. CDL posudba za novije naslove.",
        "icon": "bi-archive",
        "color": "#06b6d4",
        "legal": "Javna domena + CDL (Controlled Digital Lending)",
        "formats": ["PDF", "EPUB", "DAISY", "Online"],
    },
    "nsk": {
        "name": "NSK Digitalna",
        "url": "https://digitalna.nsk.hr/",
        "description": "Digitalizirana hrvatska bastina.",
        "icon": "bi-building-check",
        "color": "#c9a84c",
        "legal": "Javna domena / NSK licenca",
        "formats": ["Online", "PDF"],
    },
}


def _fetch_json(url, timeout=10):
    """Safe JSON fetch with timeout."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LIMITConnect/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (json.JSONDecodeError, ValueError):
        return None


@login_required
def source_hub(request):
    """Hub stranica — pregled svih izvora s live pretragom."""
    return render(request, "library/source_hub.html", {
        "sources": SOURCES,
    })


@login_required
def search_gutenberg(request):
    """Pretrazi Project Gutenberg API."""
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"results": [], "total": 0})

    url = f"https://gutendex.com/books/?search={urllib.parse.quote(q)}&languages=hr,en,de"
    data = _fetch_json(url, timeout=15)
    if not data:
        return JsonResponse({"error": "Gutenberg API nedostupan"}, status=502)

    results = []
    for b in data.get("results", [])[:20]:
        authors = ", ".join(a.get("name", "") for a in b.get("authors", []))
        cover = b.get("formats", {}).get("image/jpeg", "")
        formats = []
        for fmt, url in b.get("formats", {}).items():
            if "epub" in fmt.lower():
                formats.append({"type": "EPUB", "url": url})
            elif "pdf" in fmt.lower() or "pdf" in url.lower():
                formats.append({"type": "PDF", "url": url})
            elif fmt == "text/html":
                formats.append({"type": "HTML", "url": url})

        results.append({
            "id": b.get("id"),
            "title": b.get("title", ""),
            "authors": authors,
            "cover": cover,
            "languages": b.get("languages", []),
            "download_count": b.get("download_count", 0),
            "formats": formats,
            "source": "gutenberg",
            "source_url": f"https://www.gutenberg.org/ebooks/{b.get('id')}",
        })

    return JsonResponse({
        "results": results,
        "total": data.get("count", 0),
        "source": "gutenberg",
    })


@login_required
def search_openlibrary(request):
    """Pretrazi OpenLibrary API."""
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"results": [], "total": 0})

    url = f"https://openlibrary.org/search.json?q={urllib.parse.quote(q)}&limit=20&language=hrv"
    data = _fetch_json(url, timeout=15)
    if not data:
        return JsonResponse({"error": "OpenLibrary API nedostupan"}, status=502)

    results = []
    for doc in data.get("docs", [])[:20]:
        cover_id = doc.get("cover_i")
        cover = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ""
        isbn_list = doc.get("isbn", [])
        isbn = isbn_list[0] if isbn_list else ""

        results.append({
            "title": doc.get("title", ""),
            "authors": ", ".join(doc.get("author_name", [])),
            "cover": cover,
            "year": doc.get("first_publish_year"),
            "isbn": isbn,
            "publisher": ", ".join(doc.get("publisher", [])[:2]),
            "source": "openlibrary",
            "source_url": f"https://openlibrary.org{doc.get('key', '')}",
            "editions": doc.get("edition_count", 0),
        })

    return JsonResponse({
        "results": results,
        "total": data.get("numFound", 0),
        "source": "openlibrary",
    })


@login_required
def import_from_source(request):
    """Uvezi knjigu iz vanjskog izvora u lokalni katalog."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    company = get_user_company(request)
    data = json.loads(request.body) if request.content_type == "application/json" else request.POST

    title = data.get("title", "").strip()
    if not title:
        return JsonResponse({"error": "Naslov je obavezan"}, status=400)

    # Check duplicate
    existing = Book.objects.filter(company=company, title__iexact=title).first()
    if existing:
        return JsonResponse({
            "error": f"Knjiga '{title}' vec postoji u katalogu (ID: {existing.pk})",
            "existing_id": existing.pk,
        }, status=409)

    # Create book
    isbn = re.sub(r"[^0-9X]", "", data.get("isbn", "").upper())
    book = Book.objects.create(
        company=company,
        title=title,
        subtitle=data.get("subtitle", "").strip(),
        isbn_13=isbn if len(isbn) == 13 else "",
        isbn_10=isbn if len(isbn) == 10 else "",
        publisher=data.get("publisher", "").strip(),
        publish_year=int(data["year"]) if data.get("year") else None,
        language=data.get("language", "hr"),
        description=data.get("description", "").strip()[:1000],
        cover_url=data.get("cover", "").strip(),
        openlibrary_key=data.get("source_url", ""),
    )

    # Author
    author_str = data.get("authors", "").strip()
    if author_str:
        for name in author_str.split(","):
            name = name.strip()
            if not name:
                continue
            parts = name.split(" ", 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else ""
            author, _ = Author.objects.get_or_create(
                company=company, first_name=first, last_name=last,
            )
            book.authors.add(author)

    # Digital copy (link to source)
    source_url = data.get("source_url", "")
    if source_url:
        BookCopy.objects.create(
            book=book,
            barcode=f"DIG-{book.pk:06d}",
            status="reference",
            condition="new",
            location=f"Digitalno: {data.get('source', 'external')}",
            notes=f"Izvor: {source_url}",
        )

    return JsonResponse({
        "success": True,
        "book_id": book.pk,
        "title": book.title,
        "message": f"'{book.title}' uvezena u katalog!",
    })
