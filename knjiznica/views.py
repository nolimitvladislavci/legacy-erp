from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponse
from datetime import timedelta
from decimal import Decimal
import csv

from core.company_utils import get_user_company
from .models import BookMeta, BookLoan, LibraryMember, BookReservation


@login_required
def dashboard(request):
    company = get_user_company(request)
    today = timezone.localdate()

    # Auto-tranzicija kasnih posudbi u overdue
    overdue_qs = BookLoan.objects.filter(
        company=company, status='borrowed', due_date__lt=today
    ).select_related('member__partner', 'item')
    for loan in overdue_qs:
        loan.transition_to('overdue', user=request.user)

    stats = {
        'active_members': LibraryMember.objects.filter(
            company=company, status__in=['active', 'junior']).count(),
        'books_borrowed': BookLoan.objects.filter(
            company=company, status='borrowed').count(),
        'overdue_count': BookLoan.objects.filter(
            company=company, status='overdue').count(),
        'waiting_reservations': BookReservation.objects.filter(
            company=company, status='waiting').count(),
    }

    recent_loans = BookLoan.objects.filter(
        company=company
    ).select_related('member__partner', 'item').order_by('-loan_date')[:10]

    overdue_loans = BookLoan.objects.filter(
        company=company, status='overdue'
    ).select_related('member__partner', 'item').order_by('due_date')

    return render(request, 'knjiznica/dashboard.html', {
        'stats': stats,
        'recent_loans': recent_loans,
        'overdue_loans': overdue_loans,
    })


@login_required
def catalog_list(request):
    company = get_user_company(request)
    from inventory.models import InventoryItem

    # Annotate is_loaned u SQL umjesto Python petlje (N+1 fix)
    active_loan_subq = BookLoan.objects.filter(
        item=OuterRef('pk'), company=company,
        status__in=['borrowed', 'overdue'],
    )
    books = InventoryItem.objects.filter(
        company=company
    ).select_related('book_meta').annotate(
        is_loaned=Exists(active_loan_subq)
    ).order_by('name')

    q = request.GET.get('q', '').strip()
    if q:
        books = books.filter(
            Q(name__icontains=q) |
            Q(book_meta__author__icontains=q) |
            Q(book_meta__isbn__icontains=q)
        )

    # Paginacija
    paginator = Paginator(books, 25)
    page = request.GET.get('page')
    books_page = paginator.get_page(page)

    return render(request, 'knjiznica/catalog_list.html', {
        'books': books_page,
        'q': q,
        'paginator': paginator,
    })


@login_required
def catalog_detail(request, pk):
    company = get_user_company(request)
    from inventory.models import InventoryItem
    book = get_object_or_404(InventoryItem, pk=pk, company=company)
    meta = getattr(book, 'book_meta', None)
    loans = BookLoan.objects.filter(
        item=book, company=company
    ).select_related('member__partner').order_by('-loan_date')[:20]
    active_loan = loans.filter(status__in=['borrowed', 'overdue']).first()

    return render(request, 'knjiznica/catalog_detail.html', {
        'book': book,
        'meta': meta,
        'loans': loans,
        'active_loan': active_loan,
    })


@login_required
def catalog_create(request):
    company = get_user_company(request)
    if request.method == 'POST':
        from inventory.models import InventoryItem
        item = InventoryItem.objects.create(
            company=company,
            name=request.POST.get('name', '').strip(),
            sku=request.POST.get('sku', '').strip() or f"BOOK-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            barcode=request.POST.get('barcode', '').strip(),
        )
        BookMeta.objects.create(
            item=item,
            isbn=request.POST.get('isbn', '').strip(),
            author=request.POST.get('author', '').strip(),
            publisher=request.POST.get('publisher', '').strip(),
            pub_year=int(request.POST['pub_year']) if request.POST.get('pub_year') else None,
            shelf_location=request.POST.get('shelf_location', '').strip(),
            is_reference='is_reference' in request.POST,
        )
        messages.success(request, f'Knjiga "{item.name}" dodana u katalog.')
        return redirect('knjiznica:catalog_list')

    return render(request, 'knjiznica/catalog_create.html')


@login_required
def member_list(request):
    company = get_user_company(request)
    members = LibraryMember.objects.filter(
        company=company
    ).select_related('partner').annotate(
        active_loans=Count('loans', filter=Q(loans__status__in=['borrowed', 'overdue']))
    ).order_by('partner__name')

    q = request.GET.get('q', '').strip()
    if q:
        members = members.filter(
            Q(partner__name__icontains=q) | Q(member_number__icontains=q)
        )

    # Paginacija
    paginator = Paginator(members, 25)
    page = request.GET.get('page')
    members_page = paginator.get_page(page)

    return render(request, 'knjiznica/member_list.html', {
        'members': members_page,
        'q': q,
        'paginator': paginator,
    })


@login_required
def member_create(request):
    company = get_user_company(request)
    if request.method == 'POST':
        partner_id = request.POST.get('partner_id')
        from partners.models import Partner
        partner = get_object_or_404(Partner, pk=partner_id, company=company)

        member = LibraryMember.objects.create(
            company=company,
            partner=partner,
            member_number=request.POST.get('member_number', '').strip(),
            membership_until=request.POST.get('membership_until'),
            status=request.POST.get('status', 'active'),
        )
        # Hash PIN ako je unesen
        raw_pin = request.POST.get('portal_pin', '').strip()
        if raw_pin:
            member.set_portal_pin(raw_pin)
        messages.success(request, f'Član "{partner.name}" kreiran s iskaznicom {member.member_number}.')
        return redirect('knjiznica:member_list')

    from partners.models import Partner
    partners = Partner.objects.filter(company=company).order_by('name')
    return render(request, 'knjiznica/member_create.html', {'partners': partners})


@login_required
def member_detail(request, pk):
    company = get_user_company(request)
    member = get_object_or_404(LibraryMember, pk=pk, company=company)
    loans = BookLoan.objects.filter(
        member=member, company=company
    ).select_related('item').order_by('-loan_date')[:30]
    reservations = BookReservation.objects.filter(
        member=member, company=company
    ).select_related('item').order_by('-reserved_at')[:10]

    return render(request, 'knjiznica/member_detail.html', {
        'member': member,
        'loans': loans,
        'reservations': reservations,
    })


@login_required
def loan_create(request):
    """Nova posudba — odaberi člana + knjigu + rok."""
    company = get_user_company(request)

    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        item_id = request.POST.get('item_id')
        due_days = int(request.POST.get('due_days', 15))

        member = get_object_or_404(LibraryMember, pk=member_id, company=company)
        from inventory.models import InventoryItem
        item = get_object_or_404(InventoryItem, pk=item_id, company=company)

        meta = getattr(item, 'book_meta', None)
        if meta and meta.is_reference:
            messages.error(request, _('Referentna građa se ne posuđuje.'))
            return redirect('knjiznica:loan_create')

        can_borrow, reason = member.can_borrow
        if not can_borrow:
            messages.error(request, f'Ne može posuditi: {reason}')
            return redirect('knjiznica:loan_create')

        active_loan = BookLoan.objects.filter(
            item=item, company=company,
            status__in=['borrowed', 'overdue']
        ).first()
        if active_loan:
            messages.error(request, f'Knjiga je već posuđena do {active_loan.due_date}.')
            return redirect('knjiznica:loan_create')

        due_date = timezone.localdate() + timedelta(days=due_days)
        BookLoan.objects.create(
            company=company,
            member=member,
            item=item,
            due_date=due_date,
            status='borrowed',
            librarian=request.user,
        )
        messages.success(request,
            f'Posudba OK: {item.name} → {member.partner.name}, rok {due_date}')
        return redirect('knjiznica:dashboard')

    members = LibraryMember.objects.filter(
        company=company, status__in=['active', 'junior']
    ).select_related('partner').order_by('partner__name')

    from inventory.models import InventoryItem
    books = InventoryItem.objects.filter(company=company).order_by('name')

    return render(request, 'knjiznica/loan_form.html', {
        'members': members,
        'books': books,
    })


@login_required
def loan_return(request, pk):
    """Povrat knjige."""
    company = get_user_company(request)
    loan = get_object_or_404(BookLoan, pk=pk, company=company)

    if loan.status not in ('borrowed', 'overdue'):
        messages.error(request, _('Ova posudba nije aktivna.'))
        return redirect('knjiznica:dashboard')

    if request.method == 'POST':
        loan.transition_to('returned', user=request.user)

        if loan.fine_total > 0:
            messages.warning(request, f'Knjiga vraćena s kaznama: {loan.fine_total}€')
        else:
            messages.success(request, _('Knjiga vraćena. Nema kazni.'))

        reservation = BookReservation.objects.filter(
            item=loan.item, company=company, status='waiting'
        ).order_by('reserved_at').first()
        if reservation:
            reservation.status = 'notified'
            reservation.notified_at = timezone.now()
            reservation.expires_at = timezone.localdate() + timedelta(days=3)
            reservation.save()
            try:
                from core.whatsapp import send_text
                phone = reservation.member.partner.phone
                if phone:
                    send_text(phone=phone, message=(
                        f'Vasa rezervacija\n'
                        f'Knjiga "{loan.item.name}" je dostupna!\n'
                        f'Preuzeti do: {reservation.expires_at}'
                    ))
            except ImportError:
                pass
            messages.info(request,
                f'Obaviješten je {reservation.member.partner.name} — čekao ovu knjigu.')

        return redirect('knjiznica:dashboard')

    return render(request, 'knjiznica/loan_return_confirm.html', {'loan': loan})


@login_required
def reservation_create(request):
    """Rezervacija knjige koja je trenutno posuđena."""
    company = get_user_company(request)

    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        item_id = request.POST.get('item_id')
        member = get_object_or_404(LibraryMember, pk=member_id, company=company)
        from inventory.models import InventoryItem
        item = get_object_or_404(InventoryItem, pk=item_id, company=company)

        existing = BookReservation.objects.filter(
            member=member, item=item, company=company, status='waiting'
        ).exists()
        if existing:
            messages.error(request, _('Član već čeka ovu knjigu.'))
            return redirect('knjiznica:catalog_list')

        BookReservation.objects.create(
            company=company, member=member, item=item
        )
        messages.success(request, f'Rezervacija kreirana za "{item.name}".')
        return redirect('knjiznica:catalog_list')

    return redirect('knjiznica:catalog_list')


@login_required
def statistics(request):
    company = get_user_company(request)
    today = timezone.localdate()
    year = int(request.GET.get('year', today.year))

    loans_year = BookLoan.objects.filter(company=company, loan_date__year=year)

    stats = {
        'year': year,
        'total_loans': loans_year.count(),
        'returned': loans_year.filter(status='returned').count(),
        'overdue': loans_year.filter(status='overdue').count(),
        'with_fines': loans_year.filter(fine_total__gt=0).count(),
        'total_fines': loans_year.aggregate(s=Sum('fine_total'))['s'] or Decimal('0.00'),
        'active_members': LibraryMember.objects.filter(
            company=company, status__in=['active', 'junior']).count(),
    }

    from inventory.models import InventoryItem
    top_books = InventoryItem.objects.filter(
        company=company, loans__loan_date__year=year
    ).annotate(
        loan_count=Count('loans')
    ).order_by('-loan_count')[:10]

    return render(request, 'knjiznica/statistics.html', {
        'stats': stats,
        'top_books': top_books,
    })


@login_required
def nsk_export(request):
    """NSK statistički export — godišnji CSV."""
    company = get_user_company(request)
    year = int(request.GET.get('year', timezone.localdate().year))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="nsk_statistika_{year}.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Knjižnica', 'OIB', 'Godina',
        'Broj članova', 'Broj posudbi', 'Broj vraćenih',
        'Knjiga s kaznama', 'Ukupne kazne (EUR)',
        'Broj aktivnih naslova',
    ])

    from inventory.models import InventoryItem
    loans = BookLoan.objects.filter(company=company, loan_date__year=year)
    total_fines = loans.aggregate(s=Sum('fine_total'))['s'] or Decimal('0.00')

    writer.writerow([
        company.name,
        getattr(company, 'oib', ''),
        year,
        LibraryMember.objects.filter(company=company, status__in=['active', 'junior']).count(),
        loans.filter(status__in=['borrowed', 'overdue', 'returned']).count(),
        loans.filter(status='returned').count(),
        loans.filter(fine_total__gt=0).count(),
        str(total_fines),
        InventoryItem.objects.filter(company=company).count(),
    ])

    return response
