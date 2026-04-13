"""
LIMIT e-Knjiznica — Views.

Dashboard, katalog, posudba/vracanje, clanovi, ISBN lookup,
import wizard, QR scan, statistika.
"""
import json
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Count, Q, F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from core.company_utils import get_user_company
from .models import (
    Author, Category, Book, BookCopy, MembershipType,
    LibraryMember, Loan, Reservation,
)


def _company(request):
    return get_user_company(request)


# ══════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════

@login_required
def dashboard(request):
    company = _company(request)
    today = timezone.now().date()

    total_books = Book.objects.filter(company=company).count()
    total_copies = BookCopy.objects.filter(book__company=company).count()
    available_copies = BookCopy.objects.filter(book__company=company, status="available").count()
    active_members = LibraryMember.objects.filter(company=company, status="active").count()

    active_loans = Loan.objects.filter(
        member__company=company, returned_date__isnull=True,
    ).count()
    overdue_loans = Loan.objects.filter(
        member__company=company, returned_date__isnull=True,
        due_date__lt=today,
    ).count()

    # Top 5 najpopularnijih knjiga
    popular = Book.objects.filter(company=company).order_by("-times_borrowed")[:5]

    # Zadnjih 10 posudbi
    recent_loans = Loan.objects.filter(
        member__company=company,
    ).select_related("member", "copy__book").order_by("-borrowed_date")[:10]

    # Rezervacije na cekanju
    pending_reservations = Reservation.objects.filter(
        member__company=company, status="pending",
    ).count()

    return render(request, "library/dashboard.html", {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "active_members": active_members,
        "active_loans": active_loans,
        "overdue_loans": overdue_loans,
        "popular": popular,
        "recent_loans": recent_loans,
        "pending_reservations": pending_reservations,
        "today": today,
    })


# ══════════════════════════════════════════════════════════
# KATALOG
# ══════════════════════════════════════════════════════════

@login_required
def book_list(request):
    company = _company(request)
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("category", "")

    qs = Book.objects.filter(company=company).prefetch_related("authors")
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(isbn_13__icontains=q) |
            Q(isbn_10__icontains=q) |
            Q(authors__last_name__icontains=q) |
            Q(publisher__icontains=q)
        ).distinct()
    if cat:
        qs = qs.filter(category_id=cat)

    categories = Category.objects.filter(company=company)

    return render(request, "library/book_list.html", {
        "books": qs[:100],
        "query": q,
        "categories": categories,
        "cat_filter": cat,
        "total": qs.count(),
    })


@login_required
def book_detail(request, pk):
    company = _company(request)
    book = get_object_or_404(Book, pk=pk, company=company)
    copies = book.copies.all()
    recent_loans = Loan.objects.filter(
        copy__book=book,
    ).select_related("member").order_by("-borrowed_date")[:10]
    reservations = book.reservations.filter(status="pending")

    return render(request, "library/book_detail.html", {
        "book": book,
        "copies": copies,
        "recent_loans": recent_loans,
        "reservations": reservations,
    })


@login_required
def book_create(request):
    company = _company(request)
    categories = Category.objects.filter(company=company)

    if request.method == "POST":
        d = request.POST
        isbn = re.sub(r"[^0-9X]", "", d.get("isbn_13", "").upper())

        book = Book.objects.create(
            company=company,
            title=d.get("title", "").strip(),
            subtitle=d.get("subtitle", "").strip(),
            isbn_13=isbn if len(isbn) == 13 else "",
            isbn_10=isbn if len(isbn) == 10 else "",
            publisher=d.get("publisher", "").strip(),
            publish_year=int(d["publish_year"]) if d.get("publish_year") else None,
            language=d.get("language", "hr"),
            pages=int(d["pages"]) if d.get("pages") else None,
            description=d.get("description", "").strip(),
            category_id=d.get("category") or None,
            cover_url=d.get("cover_url", "").strip(),
        )

        # Autor
        author_name = d.get("author_name", "").strip()
        if author_name:
            parts = author_name.split(" ", 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else ""
            author, _ = Author.objects.get_or_create(
                company=company, first_name=first, last_name=last,
            )
            book.authors.add(author)

        # Primjerak
        barcode = d.get("barcode", "").strip()
        if barcode:
            BookCopy.objects.create(
                book=book, barcode=barcode,
                location=d.get("location", "").strip(),
                status="available",
            )

        messages.success(request, f'Knjiga "{book.title}" dodana u katalog.')
        return redirect("library:book_detail", pk=book.pk)

    return render(request, "library/book_form.html", {
        "categories": categories, "mode": "create",
    })


# ══════════════════════════════════════════════════════════
# ISBN AUTO-FILL (OpenLibrary API)
# ══════════════════════════════════════════════════════════

@login_required
def isbn_lookup(request):
    """AJAX endpoint: ISBN -> metadata iz OpenLibrary."""
    isbn = re.sub(r"[^0-9X]", "", request.GET.get("isbn", "").upper())
    if not isbn or len(isbn) not in (10, 13):
        return JsonResponse({"error": "Neispravan ISBN"}, status=400)

    import urllib.request
    import urllib.error

    # OpenLibrary API
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LIMITConnect/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError):
        return JsonResponse({"error": "OpenLibrary API nedostupan"}, status=502)

    key = f"ISBN:{isbn}"
    if key not in data:
        # Fallback: Google Books
        gurl = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        try:
            req = urllib.request.Request(gurl, headers={"User-Agent": "LIMITConnect/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                gdata = json.loads(resp.read().decode())
            if gdata.get("totalItems", 0) > 0:
                vol = gdata["items"][0]["volumeInfo"]
                return JsonResponse({
                    "found": True,
                    "source": "google",
                    "title": vol.get("title", ""),
                    "subtitle": vol.get("subtitle", ""),
                    "authors": ", ".join(vol.get("authors", [])),
                    "publisher": vol.get("publisher", ""),
                    "publish_year": vol.get("publishedDate", "")[:4],
                    "pages": vol.get("pageCount"),
                    "description": vol.get("description", "")[:500],
                    "cover_url": vol.get("imageLinks", {}).get("thumbnail", ""),
                    "language": vol.get("language", ""),
                })
        except (json.JSONDecodeError, ValueError):
            pass
        return JsonResponse({"found": False, "error": "Knjiga nije pronadjena"})

    info = data[key]
    authors = ", ".join(a.get("name", "") for a in info.get("authors", []))
    cover = info.get("cover", {}).get("medium", "")

    return JsonResponse({
        "found": True,
        "source": "openlibrary",
        "title": info.get("title", ""),
        "subtitle": info.get("subtitle", ""),
        "authors": authors,
        "publisher": info.get("publishers", [{}])[0].get("name", "") if info.get("publishers") else "",
        "publish_year": str(info.get("publish_date", ""))[-4:],
        "pages": info.get("number_of_pages"),
        "description": "",
        "cover_url": cover,
        "language": "",
        "openlibrary_key": info.get("key", ""),
    })


# ══════════════════════════════════════════════════════════
# POSUDBA / VRACANJE
# ══════════════════════════════════════════════════════════

@login_required
def loan_checkout(request):
    """Posudba: skeniraj QR clana + barcode knjige."""
    company = _company(request)

    if request.method == "POST":
        member_input = request.POST.get("member", "").strip()
        barcode = request.POST.get("barcode", "").strip()

        # Pronadji clana po broju, QR tokenu, ili OIB-u
        member = LibraryMember.objects.filter(company=company).filter(
            Q(member_number=member_input) |
            Q(qr_token=member_input) |
            Q(oib=member_input)
        ).first()

        if not member:
            messages.error(request, _("Clan nije pronadjen."))
            return redirect("library:loan_checkout")

        if not member.can_borrow:
            reason = ""
            if member.status != "active":
                reason = f"Status: {member.get_status_display()}"
            elif member.outstanding_fines > Decimal("5.00"):
                reason = f"Dugovanje: {member.outstanding_fines} EUR"
            else:
                reason = "Dosegnut max broj posudbi"
            messages.error(request, f"Clan {member} ne moze posuditi. {reason}")
            return redirect("library:loan_checkout")

        copy = BookCopy.objects.filter(barcode=barcode, book__company=company).first()
        if not copy:
            messages.error(request, f"Primjerak s barcodom '{barcode}' nije pronadjen.")
            return redirect("library:loan_checkout")

        if copy.status != "available":
            messages.error(request, f"Primjerak nije dostupan (status: {copy.get_status_display()}).")
            return redirect("library:loan_checkout")

        # Izracunaj rok
        loan_days = 21
        if member.membership_type:
            loan_days = member.membership_type.loan_days
        due = timezone.now().date() + timedelta(days=loan_days)

        loan = Loan.objects.create(
            member=member,
            copy=copy,
            due_date=due,
            issued_by=request.user,
        )
        copy.status = "borrowed"
        copy.save(update_fields=["status"])

        # Update stats
        member.total_borrowed = F("total_borrowed") + 1
        member.save(update_fields=["total_borrowed"])
        copy.book.times_borrowed = F("times_borrowed") + 1
        copy.book.save(update_fields=["times_borrowed"])

        messages.success(
            request,
            f'{copy.book.title} posudjena clanu {member}. Rok: {due.strftime("%d.%m.%Y")}',
        )
        return redirect("library:loan_checkout")

    return render(request, "library/loan_checkout.html")


@login_required
def loan_return(request):
    """Vracanje: skeniraj barcode knjige."""
    company = _company(request)
    returned_info = None

    if request.method == "POST":
        barcode = request.POST.get("barcode", "").strip()

        copy = BookCopy.objects.filter(barcode=barcode, book__company=company).first()
        if not copy:
            messages.error(request, f"Primjerak '{barcode}' nije pronadjen.")
            return redirect("library:loan_return")

        loan = Loan.objects.filter(
            copy=copy, returned_date__isnull=True,
        ).select_related("member").first()

        if not loan:
            messages.warning(request, f"Nema aktivne posudbe za '{barcode}'.")
            return redirect("library:loan_return")

        # Vrati
        loan.returned_date = timezone.now()
        loan.status = "returned"
        loan.calculate_fine()
        loan.save()

        copy.status = "available"
        copy.save(update_fields=["status"])

        # Fine
        if loan.fine_amount > 0:
            loan.member.total_fines = F("total_fines") + loan.fine_amount
            loan.member.save(update_fields=["total_fines"])
            messages.warning(
                request,
                f"Kasnjenje {loan.days_overdue} dana. Kazna: {loan.fine_amount} EUR",
            )

        # Check reservations
        pending_res = Reservation.objects.filter(
            book=copy.book, status="pending",
        ).order_by("reserved_date").first()
        if pending_res:
            pending_res.status = "ready"
            pending_res.pickup_deadline = timezone.now().date() + timedelta(days=3)
            pending_res.notified_date = timezone.now()
            pending_res.save()
            messages.info(
                request,
                f"Rezervacija: {pending_res.member} ceka ovu knjigu!",
            )

        returned_info = {
            "book": copy.book.title,
            "member": str(loan.member),
            "days_overdue": loan.days_overdue,
            "fine": loan.fine_amount,
        }
        messages.success(request, f'{copy.book.title} vracena od {loan.member}.')

    return render(request, "library/loan_return.html", {
        "returned_info": returned_info,
    })


@login_required
def loan_renew(request, pk):
    """Produljenje posudbe."""
    loan = get_object_or_404(Loan, pk=pk, member__company=_company(request))
    if loan.returned_date:
        messages.error(request, _("Ova posudba je vec vracena."))
    elif loan.renewed_count >= 2:
        messages.error(request, _("Maksimalno 2 produljenja."))
    else:
        days = 14
        if loan.member.membership_type:
            days = loan.member.membership_type.loan_days
        loan.due_date = timezone.now().date() + timedelta(days=days)
        loan.renewed_count += 1
        loan.save(update_fields=["due_date", "renewed_count"])
        messages.success(request, f'Produljeno do {loan.due_date.strftime("%d.%m.%Y")}.')
    return redirect(request.META.get("HTTP_REFERER", reverse("library:dashboard")))


# ══════════════════════════════════════════════════════════
# CLANOVI
# ══════════════════════════════════════════════════════════

@login_required
def member_list(request):
    company = _company(request)
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active")

    qs = LibraryMember.objects.filter(company=company)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(member_number__icontains=q) |
            Q(oib__icontains=q)
        )

    return render(request, "library/member_list.html", {
        "members": qs[:100],
        "query": q,
        "status_filter": status,
    })


@login_required
def member_detail(request, pk):
    company = _company(request)
    member = get_object_or_404(LibraryMember, pk=pk, company=company)
    active_loans = member.loans.filter(returned_date__isnull=True).select_related("copy__book")
    history = member.loans.filter(returned_date__isnull=False).select_related("copy__book").order_by("-returned_date")[:20]
    reservations = member.reservations.filter(status__in=["pending", "ready"])

    return render(request, "library/member_detail.html", {
        "member": member,
        "active_loans": active_loans,
        "history": history,
        "reservations": reservations,
    })


@login_required
def member_create(request):
    company = _company(request)
    types = MembershipType.objects.filter(company=company)

    if request.method == "POST":
        d = request.POST
        # Auto-generate member number
        last = LibraryMember.objects.filter(company=company).order_by("-member_number").first()
        if last and last.member_number.isdigit():
            next_num = str(int(last.member_number) + 1).zfill(6)
        else:
            next_num = "000001"

        member = LibraryMember.objects.create(
            company=company,
            first_name=d.get("first_name", "").strip(),
            last_name=d.get("last_name", "").strip(),
            email=d.get("email", "").strip(),
            phone=d.get("phone", "").strip(),
            oib=d.get("oib", "").strip(),
            date_of_birth=d.get("date_of_birth") or None,
            address=d.get("address", "").strip(),
            membership_type_id=d.get("membership_type") or None,
            member_number=next_num,
            membership_start=timezone.now().date(),
            membership_end=timezone.now().date() + timedelta(days=365),
        )
        messages.success(request, f"Clan {member} upisan. Broj: {member.member_number}")
        return redirect("library:member_detail", pk=member.pk)

    return render(request, "library/member_form.html", {
        "types": types, "mode": "create",
    })


@login_required
def member_qr(request, pk):
    """QR iskaznica clana (JSON za frontend rendering)."""
    member = get_object_or_404(LibraryMember, pk=pk, company=_company(request))
    return JsonResponse({
        "member_number": member.member_number,
        "name": str(member),
        "qr_data": str(member.qr_token),
        "membership_type": str(member.membership_type) if member.membership_type else "",
        "valid_until": member.membership_end.isoformat() if member.membership_end else "",
    })


# ══════════════════════════════════════════════════════════
# QR SCAN (za posudbu — AJAX)
# ══════════════════════════════════════════════════════════

@login_required
def qr_scan_member(request):
    """AJAX: QR token -> member info."""
    token = request.GET.get("token", "").strip()
    company = _company(request)
    member = LibraryMember.objects.filter(company=company, qr_token=token).first()
    if not member:
        return JsonResponse({"found": False})
    return JsonResponse({
        "found": True,
        "id": member.pk,
        "name": str(member),
        "member_number": member.member_number,
        "status": member.status,
        "can_borrow": member.can_borrow,
        "active_loans": member.active_loans_count,
        "max_books": member.membership_type.max_books if member.membership_type else 5,
        "outstanding_fines": str(member.outstanding_fines),
    })


# ══════════════════════════════════════════════════════════
# STATISTIKA
# ══════════════════════════════════════════════════════════

@login_required
def statistics(request):
    company = _company(request)
    today = timezone.now().date()

    # Posudbe po mjesecima (zadnjih 12)
    monthly_stats = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        count = Loan.objects.filter(
            member__company=company,
            borrowed_date__year=y,
            borrowed_date__month=m,
        ).count()
        monthly_stats.append({"month": f"{m}/{y}", "count": count})

    # Top 10 knjiga
    top_books = Book.objects.filter(company=company).order_by("-times_borrowed")[:10]

    # Top 10 clanova
    top_members = LibraryMember.objects.filter(company=company).order_by("-total_borrowed")[:10]

    # Po kategorijama
    cat_stats = Category.objects.filter(company=company).annotate(
        book_count=Count("books"),
    ).order_by("-book_count")[:10]

    return render(request, "library/statistics.html", {
        "monthly_stats": monthly_stats,
        "top_books": top_books,
        "top_members": top_members,
        "cat_stats": cat_stats,
    })


# ══════════════════════════════════════════════════════════
# OVERDUE MANAGEMENT
# ══════════════════════════════════════════════════════════

@login_required
def overdue_list(request):
    company = _company(request)
    today = timezone.now().date()
    overdue = Loan.objects.filter(
        member__company=company,
        returned_date__isnull=True,
        due_date__lt=today,
    ).select_related("member", "copy__book").order_by("due_date")

    return render(request, "library/overdue_list.html", {
        "overdue_loans": overdue,
        "today": today,
    })
