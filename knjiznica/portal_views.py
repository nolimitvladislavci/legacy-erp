"""
Javni portal knjižnice — BEZ LIMIT Connect branding-a.
Pristup: /portal/<slug>/  (slug = company.booking_slug)
Bez login-a: katalog, događanja, medijski sadržaj
S PIN-om: roditeljski dashboard, djeca, bedževi
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta

from companies.models import Company
from .models import (
    BookMeta, BookLoan, LibraryMember, BookReservation,
    ChildReader, BadgeDefinition, EarnedBadge, ReadingLog,
    MediaContent, FamilyChallenge,
)


def _get_library(slug):
    """Dohvati knjižnicu po slug-u."""
    return get_object_or_404(Company, booking_slug=slug)


def _get_session_member(request, company):
    """Dohvati člana iz session-a (PIN login)."""
    member_id = request.session.get(f'library_member_{company.pk}')
    if member_id:
        try:
            return LibraryMember.objects.select_related('partner').get(
                pk=member_id, company=company
            )
        except LibraryMember.DoesNotExist:
            pass
    return None


# ─── JAVNE STRANICE (bez logina) ───────────────────────

def portal_home(request, slug):
    company = _get_library(slug)
    member = _get_session_member(request, company)

    from inventory.models import InventoryItem
    new_books = InventoryItem.objects.filter(
        company=company
    ).select_related('book_meta').order_by('-pk')[:8]

    stats = {
        'total_books': InventoryItem.objects.filter(company=company).count(),
        'total_members': LibraryMember.objects.filter(
            company=company, status__in=['active', 'junior']).count(),
        'active_loans': BookLoan.objects.filter(
            company=company, status='borrowed').count(),
        'total_children': ChildReader.objects.filter(company=company).count(),
    }

    media = MediaContent.objects.filter(
        company=company, is_published=True
    ).order_by('-created_at')[:4]

    top_readers = ChildReader.objects.filter(
        company=company
    ).order_by('-books_read')[:5]

    return render(request, 'knjiznica/portal/home.html', {
        'company': company,
        'slug': slug,
        'member': member,
        'new_books': new_books,
        'stats': stats,
        'media': media,
        'top_readers': top_readers,
    })


def portal_catalog(request, slug):
    company = _get_library(slug)
    member = _get_session_member(request, company)

    from inventory.models import InventoryItem
    books = InventoryItem.objects.filter(
        company=company
    ).select_related('book_meta').order_by('name')

    q = request.GET.get('q', '').strip()
    tier = request.GET.get('tier', '')
    genre = request.GET.get('genre', '')

    if q:
        books = books.filter(
            Q(name__icontains=q) |
            Q(book_meta__author__icontains=q) |
            Q(book_meta__isbn__icontains=q)
        )
    if tier:
        books = books.filter(book_meta__age_tier=tier)
    if genre:
        books = books.filter(book_meta__genre__icontains=genre)

    for book in books:
        book.is_loaned = BookLoan.objects.filter(
            item=book, company=company, status__in=['borrowed', 'overdue']
        ).exists()

    return render(request, 'knjiznica/portal/catalog.html', {
        'company': company, 'slug': slug, 'member': member,
        'books': books, 'q': q, 'tier': tier, 'genre': genre,
    })


def portal_book_detail(request, slug, pk):
    company = _get_library(slug)
    member = _get_session_member(request, company)

    from inventory.models import InventoryItem
    book = get_object_or_404(InventoryItem, pk=pk, company=company)
    meta = getattr(book, 'book_meta', None)
    active_loan = BookLoan.objects.filter(
        item=book, company=company, status__in=['borrowed', 'overdue']
    ).first()
    reviews = ReadingLog.objects.filter(
        item=book, company=company, short_review__gt=''
    ).select_related('child').order_by('-read_date')[:10]
    media = MediaContent.objects.filter(
        related_book=book, company=company, is_published=True
    )

    return render(request, 'knjiznica/portal/book_detail.html', {
        'company': company, 'slug': slug, 'member': member,
        'book': book, 'meta': meta, 'active_loan': active_loan,
        'reviews': reviews, 'media': media,
    })


def portal_media(request, slug):
    company = _get_library(slug)
    member = _get_session_member(request, company)
    tier = request.GET.get('tier', '')

    media = MediaContent.objects.filter(
        company=company, is_published=True
    ).order_by('-created_at')

    if tier:
        media = media.filter(Q(tier=tier) | Q(tier=''))

    return render(request, 'knjiznica/portal/media.html', {
        'company': company, 'slug': slug, 'member': member,
        'media': media, 'tier': tier,
    })


def portal_media_watch(request, slug, pk):
    company = _get_library(slug)
    member = _get_session_member(request, company)
    item = get_object_or_404(MediaContent, pk=pk, company=company, is_published=True)
    item.view_count += 1
    item.save(update_fields=['view_count'])

    return render(request, 'knjiznica/portal/media_watch.html', {
        'company': company, 'slug': slug, 'member': member,
        'item': item,
    })


def portal_badges(request, slug):
    company = _get_library(slug)
    badges = BadgeDefinition.objects.filter(is_active=True).order_by('sort_order')

    return render(request, 'knjiznica/portal/badges.html', {
        'company': company, 'slug': slug, 'badges': badges,
    })


# ─── PIN LOGIN ──────────────────────────────────────────

def portal_login(request, slug):
    company = _get_library(slug)
    error = ''

    if request.method == 'POST':
        member_number = request.POST.get('member_number', '').strip()
        pin = request.POST.get('pin', '').strip()

        try:
            member = LibraryMember.objects.get(
                company=company, member_number=member_number
            )
            if member.portal_pin and member.portal_pin == pin:
                request.session[f'library_member_{company.pk}'] = member.pk
                return redirect('knjiznica:portal_family', slug=slug)
            else:
                error = 'Neispravan PIN.'
        except LibraryMember.DoesNotExist:
            error = 'Broj iskaznice nije pronađen.'

    return render(request, 'knjiznica/portal/login.html', {
        'company': company, 'slug': slug, 'error': error,
    })


def portal_logout(request, slug):
    company = _get_library(slug)
    request.session.pop(f'library_member_{company.pk}', None)
    return redirect('knjiznica:portal_home', slug=slug)


# ─── RODITELJSKI DASHBOARD ─────────────────────────────

def portal_family(request, slug):
    company = _get_library(slug)
    member = _get_session_member(request, company)
    if not member:
        return redirect('knjiznica:portal_login', slug=slug)

    children = ChildReader.objects.filter(
        parent=member, company=company
    ).prefetch_related('badges__badge')

    active_loans = BookLoan.objects.filter(
        member=member, company=company, status__in=['borrowed', 'overdue']
    ).select_related('item')

    challenges = FamilyChallenge.objects.filter(
        parent=member, company=company, status='active'
    )

    return render(request, 'knjiznica/portal/family.html', {
        'company': company, 'slug': slug, 'member': member,
        'children': children, 'active_loans': active_loans,
        'challenges': challenges,
    })


def portal_child_detail(request, slug, pk):
    company = _get_library(slug)
    member = _get_session_member(request, company)
    if not member:
        return redirect('knjiznica:portal_login', slug=slug)

    child = get_object_or_404(ChildReader, pk=pk, parent=member, company=company)
    logs = ReadingLog.objects.filter(child=child).order_by('-read_date')[:20]
    badges = EarnedBadge.objects.filter(child=child).select_related('badge').order_by('-earned_at')
    all_badges = BadgeDefinition.objects.filter(is_active=True)

    return render(request, 'knjiznica/portal/child_detail.html', {
        'company': company, 'slug': slug, 'member': member,
        'child': child, 'logs': logs, 'badges': badges,
        'all_badges': all_badges,
    })


def portal_log_reading(request, slug):
    """Roditelj bilježi da je dijete pročitalo knjigu."""
    company = _get_library(slug)
    member = _get_session_member(request, company)
    if not member:
        return redirect('knjiznica:portal_login', slug=slug)

    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        item_id = request.POST.get('item_id', '').strip()
        custom_title = request.POST.get('custom_title', '').strip()
        rating = int(request.POST.get('rating', 0))
        review = request.POST.get('review', '').strip()

        child = get_object_or_404(ChildReader, pk=child_id, parent=member, company=company)

        item = None
        if item_id:
            from inventory.models import InventoryItem
            try:
                item = InventoryItem.objects.get(pk=item_id, company=company)
            except InventoryItem.DoesNotExist:
                pass

        ReadingLog.objects.create(
            company=company,
            child=child,
            item=item,
            custom_title=custom_title if not item else '',
            rating=rating,
            short_review=review,
        )
        return redirect('knjiznica:portal_child_detail', slug=slug, pk=child.pk)

    children = ChildReader.objects.filter(parent=member, company=company)
    from inventory.models import InventoryItem
    books = InventoryItem.objects.filter(company=company).order_by('name')

    return render(request, 'knjiznica/portal/log_reading.html', {
        'company': company, 'slug': slug, 'member': member,
        'children': children, 'books': books,
    })
