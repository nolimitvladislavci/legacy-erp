"""
Javni portal knjiznice — public-facing, BEZ login-a za pretragu.
Rezervacija i clanski portal zahtijevaju prijavu roditelja.
"""
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import (
    Book,
    Category,
    LibraryMember,
    Loan,
    Reservation,
)


def public_home(request, slug):
    """Naslovnica javnog portala knjiznice."""
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)

    new_books = Book.objects.filter(company=company).order_by("-created_at")[:8]
    popular = Book.objects.filter(company=company, times_borrowed__gt=0).order_by("-times_borrowed")[:8]
    categories = Category.objects.filter(company=company, parent__isnull=True)
    total_books = Book.objects.filter(company=company).count()
    total_members = LibraryMember.objects.filter(company=company, status="active").count()

    return render(request, "library/public/home.html", {
        "company": company,
        "slug": slug,
        "new_books": new_books,
        "popular": popular,
        "categories": categories,
        "total_books": total_books,
        "total_members": total_members,
    })


def public_search(request, slug):
    """AJAX pretraga kataloga — javna."""
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("category", "")
    page = int(request.GET.get("page", 1))
    per_page = 20

    qs = Book.objects.filter(company=company).prefetch_related("authors")
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(isbn_13__icontains=q) |
            Q(authors__last_name__icontains=q) |
            Q(publisher__icontains=q)
        ).distinct()
    if cat:
        qs = qs.filter(category_id=cat)

    total = qs.count()
    books = qs[(page-1)*per_page:page*per_page]

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        results = [{
            "id": b.pk,
            "title": b.title,
            "subtitle": b.subtitle,
            "authors": b.author_display,
            "publisher": b.publisher,
            "year": b.publish_year,
            "cover": b.cover_url or "",
            "available": b.available_copies,
            "total": b.total_copies,
            "isbn": b.isbn_13,
        } for b in books]
        return JsonResponse({"results": results, "total": total, "page": page})

    categories = Category.objects.filter(company=company, parent__isnull=True)
    return render(request, "library/public/search.html", {
        "company": company,
        "slug": slug,
        "books": books,
        "query": q,
        "categories": categories,
        "total": total,
        "cat_filter": cat,
    })


def public_book(request, slug, pk):
    """Detalj knjige — javni."""
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)
    book = get_object_or_404(Book, pk=pk, company=company)
    copies = book.copies.all()
    available = copies.filter(status="available").count()

    return render(request, "library/public/book_detail.html", {
        "company": company,
        "slug": slug,
        "book": book,
        "copies": copies,
        "available": available,
    })


def public_reserve(request, slug, pk):
    """Rezervacija knjige — zahtijeva prijavu."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Prijavite se za rezervaciju."}, status=401)

    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)
    book = get_object_or_404(Book, pk=pk, company=company)

    member = LibraryMember.objects.filter(
        company=company, user=request.user, status="active",
    ).first()
    if not member:
        return JsonResponse({"error": "Niste clan ove knjiznice."}, status=403)

    existing = Reservation.objects.filter(
        member=member, book=book, status__in=["pending", "ready"],
    ).exists()
    if existing:
        return JsonResponse({"error": "Vec imate aktivnu rezervaciju za ovu knjigu."}, status=400)

    Reservation.objects.create(member=member, book=book)
    return JsonResponse({"success": True, "message": "Knjiga rezervirana! Javit cemo vam kad bude dostupna."})


def public_member_portal(request, slug):
    """Clanski portal — moje posudbe, rezervacije, djecji profili."""
    from companies.models import Company
    company = get_object_or_404(Company, booking_slug=slug)

    if not request.user.is_authenticated:
        return render(request, "library/public/portal_login.html", {
            "company": company, "slug": slug,
        })

    member = LibraryMember.objects.filter(
        company=company, user=request.user,
    ).first()
    if not member:
        return render(request, "library/public/portal_no_access.html", {
            "company": company, "slug": slug,
        })

    active_loans = Loan.objects.filter(
        member=member, returned_date__isnull=True,
    ).select_related("copy__book", "reader_profile")

    history = Loan.objects.filter(
        member=member, returned_date__isnull=False,
    ).select_related("copy__book").order_by("-returned_date")[:20]

    reservations = Reservation.objects.filter(
        member=member, status__in=["pending", "ready"],
    ).select_related("book")

    children = member.reader_profiles.filter(is_active=True)

    return render(request, "library/public/portal_home.html", {
        "company": company,
        "slug": slug,
        "member": member,
        "active_loans": active_loans,
        "history": history,
        "reservations": reservations,
        "children": children,
    })
