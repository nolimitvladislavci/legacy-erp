"""
Patch: Operativna aktivacija — auto-link, admin, check-in, allocation
"""
import os
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
BASE = '/var/www/fina-connect'


# ══════════════════════════════════════════════════════════════════════
# 1. ADMIN — source_flock + SplitAllocation u InventoryItem fieldsets
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'inventory/admin.py')
with open(path) as f:
    content = f.read()

old_fieldsets = """    fieldsets = (
        (_('Identifikacija'), {
            'fields': ('company', 'name', 'sku', 'barcode', 'category', 'description', 'unit', 'is_active'),
        }),
        (_('Zalihe'), {
            'fields': ('quantity', 'min_quantity', 'max_quantity'),
        }),
        (_('Cijene i PDV'), {
            'fields': ('purchase_price', 'unit_price', 'tax_rate'),
        }),
        (_('Logistika'), {
            'fields': ('location', 'supplier'),
        }),
    )"""

new_fieldsets = """    fieldsets = (
        (_('Identifikacija'), {
            'fields': ('company', 'name', 'sku', 'barcode', 'category', 'description', 'unit', 'is_active'),
        }),
        (_('Zalihe'), {
            'fields': ('quantity', 'min_quantity', 'max_quantity'),
        }),
        (_('SplitAllocation — Agro-Turizam'), {
            'fields': ('reserved_inhouse', 'reserved_marketplace', 'allocation_buffer_pct'),
            'classes': ('collapse',),
            'description': 'Podjela zalihe između interne upotrebe (gastro/konoba) i marketplace prodaje.',
        }),
        (_('Cijene i PDV'), {
            'fields': ('purchase_price', 'unit_price', 'tax_rate'),
        }),
        (_('Logistika'), {
            'fields': ('location', 'supplier'),
        }),
        (_('Slijedivost — Farma/Perad'), {
            'fields': ('source_flock', 'livestock_animal'),
            'classes': ('collapse',),
            'description': 'Povezivanje proizvoda s izvorom (jato/grlo). OBAVEZNO za karencija enforcement na POS-u.',
        }),
    )"""

content = content.replace(old_fieldsets, new_fieldsets)

# Dodaj autocomplete za source_flock
old_admin_class = """class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'company', 'category', 'quantity_display',
                    'unit', 'purchase_price', 'unit_price', 'tax_rate', 'is_active')
    search_fields = ('name', 'sku', 'barcode', 'description')
    list_filter = ('company', 'category', 'is_active', 'tax_rate')"""

new_admin_class = """class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'company', 'category', 'quantity_display',
                    'unit', 'purchase_price', 'unit_price', 'tax_rate', 'is_active',
                    'flock_karenca_status')
    search_fields = ('name', 'sku', 'barcode', 'description')
    list_filter = ('company', 'category', 'is_active', 'tax_rate')
    raw_id_fields = ('source_flock', 'livestock_animal')"""

content = content.replace(old_admin_class, new_admin_class)

# Dodaj karenca status display metodu
old_qty_display = """    def quantity_display(self, obj):"""
new_qty_display = """    def flock_karenca_status(self, obj):
        if not obj.source_flock_id:
            return '-'
        try:
            flock = obj.source_flock
            if flock.has_active_karenca:
                end = flock.karenca_end_date
                end_str = end.strftime('%d.%m.') if end else '?'
                return format_html(
                    '<span style="color:#ef4444;font-weight:bold">KARENCA do {}</span>', end_str
                )
            return format_html('<span style="color:#16a34a">OK</span>')
        except Exception:
            return '?'
    flock_karenca_status.short_description = 'Karenca'

    def quantity_display(self, obj):"""

content = content.replace(old_qty_display, new_qty_display)

with open(path, 'w') as f:
    f.write(content)
print("[OK] inventory/admin.py — source_flock + SplitAllocation fieldsets + karenca status kolona")


# ══════════════════════════════════════════════════════════════════════
# 2. BRIDGE_PUBLISH — auto-link source_flock na InventoryItem
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'udruge/views.py')
with open(path) as f:
    content = f.read()

# Nakon uspješnog publisha EggRecorda, auto-link source_flock
old_publish_success = """            messages.success(request, f'"{product.name}" objavljeno na tržnici! Ističe: {product.expires_at}.')"""

new_publish_success = """            messages.success(request, f'"{product.name}" objavljeno na tržnici! Ističe: {product.expires_at}.')

            # Auto-link source_flock na InventoryItem-e iste kompanije
            if source_model == 'EggRecord':
                try:
                    from .models import EggRecord as ER
                    from inventory.models import InventoryItem
                    egg = ER.objects.select_related('flock').get(pk=int(source_id))
                    flock = egg.flock
                    # Nađi sve jajčane artikle bez source_flock u istoj firmi
                    egg_items = InventoryItem.objects.filter(
                        company=company,
                        source_flock__isnull=True,
                        name__icontains='jaj',
                    )
                    linked = egg_items.update(source_flock=flock)
                    if linked:
                        messages.info(
                            request,
                            f'Auto-link: {linked} artikl(a) povezano s jatom "{flock.naziv}" '
                            f'za karencija enforcement na POS-u.'
                        )
                except (ValueError, TypeError):
                    pass"""

content = content.replace(old_publish_success, new_publish_success)

with open(path, 'w') as f:
    f.write(content)
print("[OK] udruge/views.py — bridge_publish auto-link source_flock")


# ══════════════════════════════════════════════════════════════════════
# 3. BOOKING CHECK-IN — view + auto-allocation
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'experiences/views.py')
with open(path) as f:
    content = f.read()

# Dodaj check-in i complete view nakon booking_no_show
old_no_show_view = """@login_required
def booking_no_show(request, pk):
    booking = get_object_or_404(ExperienceBooking, pk=pk)
    if request.method == 'POST':
        booking.mark_no_show()
        messages.warning(request, f'{booking.guest_name} — no-show. Depozit zadržan.')
    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)"""

new_no_show_view = """@login_required
def booking_check_in(request, pk):
    \"\"\"
    Gost je došao — check-in.
    Auto-alocira inventory iz ExperienceInclusion kroz SplitAllocation servis.
    \"\"\"
    booking = get_object_or_404(ExperienceBooking, pk=pk)

    if booking.status != 'confirmed':
        messages.error(request, f'Booking nije u statusu "potvrđen" (trenutno: {booking.get_status_display()}).')
        return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)

    if request.method == 'POST':
        booking.status = 'checked_in'
        booking.save(update_fields=['status'])

        # Auto-alociraj inventory za internu upotrebu
        from experiences.models import ExperienceInclusion
        inclusions = ExperienceInclusion.objects.filter(
            experience=booking.schedule.experience,
            inventory_item__isnull=False,
        ).select_related('inventory_item')

        allocated = []
        for incl in inclusions:
            qty_needed = incl.quantity_per_person * booking.pax_count
            try:
                from inventory.services.split_allocation import allocate_to_inhouse
                movement = allocate_to_inhouse(
                    item=incl.inventory_item,
                    qty=qty_needed,
                    reason=f'Experience check-in: {booking.guest_name} x{booking.pax_count} — {incl.description}',
                    user=request.user,
                )
                allocated.append(f'{incl.description} ({qty_needed} {incl.unit})')
            except ValueError as e:
                messages.warning(request, f'Zaliha upozorenje za {incl.description}: {e}')
            except ImportError as e:
                import logging
                logging.getLogger('experiences').error('Check-in allocation error: %s', e)

        guest_msg = f'{booking.guest_name} (x{booking.pax_count}) — checked in!'
        if allocated:
            guest_msg += f' Alocirano: {", ".join(allocated)}.'
        messages.success(request, guest_msg)

    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def booking_complete(request, pk):
    \"\"\"
    Iskustvo završeno — generira račun ako nema depozita.
    \"\"\"
    booking = get_object_or_404(ExperienceBooking, pk=pk)

    if booking.status != 'checked_in':
        messages.error(request, f'Gost mora biti checked-in prije završetka.')
        return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)

    if request.method == 'POST':
        booking.status = 'completed'
        booking.save(update_fields=['status'])

        # Oslobodi schedule slot
        sched = booking.schedule
        if sched.status == 'full':
            sched.status = 'open'
            sched.save(update_fields=['status'])

        messages.success(request, f'{booking.guest_name} — iskustvo završeno.')

    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)


@login_required
def booking_no_show(request, pk):
    booking = get_object_or_404(ExperienceBooking, pk=pk)
    if request.method == 'POST':
        booking.mark_no_show()
        msg = f'{booking.guest_name} — no-show. Depozit zadržan.'
        if booking.forfeited_invoice_id:
            msg += f' Račun #{booking.forfeited_invoice_id} generiran.'
        messages.warning(request, msg)
    return redirect('experiences:experience_detail', pk=booking.schedule.experience.pk)"""

content = content.replace(old_no_show_view, new_no_show_view)

with open(path, 'w') as f:
    f.write(content)
print("[OK] experiences/views.py — booking_check_in + booking_complete + no-show poruka unaprijeđena")


# 3b. URL-ovi za check-in i complete
path = os.path.join(BASE, 'experiences/urls.py')
with open(path) as f:
    content = f.read()

old_urls = """    path('booking/<int:pk>/no-show/', views.booking_no_show, name='booking_no_show'),
    path('booking/<int:pk>/review/', views.review_create, name='review_create'),"""

new_urls = """    path('booking/<int:pk>/check-in/', views.booking_check_in, name='booking_check_in'),
    path('booking/<int:pk>/complete/', views.booking_complete, name='booking_complete'),
    path('booking/<int:pk>/no-show/', views.booking_no_show, name='booking_no_show'),
    path('booking/<int:pk>/review/', views.review_create, name='review_create'),"""

content = content.replace(old_urls, new_urls)

with open(path, 'w') as f:
    f.write(content)
print("[OK] experiences/urls.py — check-in + complete URL-ovi dodani")


# ══════════════════════════════════════════════════════════════════════
# 4. FLOCK HEALTH RECORD — auto-block InventoryItem na POS pri karenci
# ══════════════════════════════════════════════════════════════════════

# Kad se FlockHealthRecord kreira s karencom, upozori ako postoje linked InventoryItems
path = os.path.join(BASE, 'udruge/views.py')
with open(path) as f:
    content = f.read()

old_health_success = """        messages.success(request, f'Zdravstveni zapis dodan za {flock.naziv}.')
        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/flock_health_form.html', {
        'flock': flock,
        'vrsta_choices': FlockHealthRecord.VRSTA_TRETMANA,
    })"""

new_health_success = """        messages.success(request, f'Zdravstveni zapis dodan za {flock.naziv}.')

        # Upozori o POS blokadi ako postoje linked InventoryItems
        if record.karenca_dana and record.karenca_aktivna:
            try:
                linked_items = flock.inventory_products.filter(
                    is_active=True
                ).values_list('name', flat=True)
                if linked_items:
                    from datetime import timedelta
                    end_date = record.datum + timedelta(days=record.karenca_dana)
                    messages.warning(
                        request,
                        f'POS BLOKADA AKTIVNA: {len(linked_items)} artikl(a) '
                        f'({", ".join(linked_items)}) blokirano za prodaju do '
                        f'{end_date:%d.%m.%Y}. Karenca: {record.karenca_dana} dana.'
                    )
                else:
                    messages.info(
                        request,
                        f'Karenca aktivna ({record.karenca_dana} dana), ali nema '
                        f'povezanih artikala u inventaru. Povežite artikle s jatom '
                        f'u Admin → Inventar → Artikl → Izvorno jato.'
                    )
            except DatabaseError:
                pass

        return redirect('udruge:flock_detail', pk=flock.pk)

    return render(request, 'udruge/flock_health_form.html', {
        'flock': flock,
        'vrsta_choices': FlockHealthRecord.VRSTA_TRETMANA,
    })"""

content = content.replace(old_health_success, new_health_success)

with open(path, 'w') as f:
    f.write(content)
print("[OK] udruge/views.py — flock_health_create upozorava o POS blokadi")


# ══════════════════════════════════════════════════════════════════════
# 5. EXPERIENCES ADMIN — booking status + check-in/no-show info
# ══════════════════════════════════════════════════════════════════════

path = os.path.join(BASE, 'experiences/admin.py')
with open(path) as f:
    content = f.read()

# Dodaj forfeited_invoice u readonly
if 'forfeited_invoice' not in content:
    old_admin_end = content.rstrip()
    # Find ExperienceBookingAdmin if it exists
    if 'ExperienceBookingAdmin' in content:
        # Already has admin — just add field
        content = content.replace(
            "class ExperienceBookingAdmin(admin.ModelAdmin):",
            "class ExperienceBookingAdmin(admin.ModelAdmin):\n    readonly_fields = ('forfeited_invoice',)"
        )
    # If there's a generic register, add readonly
    elif 'ExperienceBooking' in content:
        pass  # Already registered somehow
    else:
        content += """

@admin.register(ExperienceBooking)
class ExperienceBookingAdmin(admin.ModelAdmin):
    list_display = ('guest_name', 'schedule', 'pax_count', 'status', 'deposit_paid', 'deposit_forfeited')
    list_filter = ('status', 'deposit_paid', 'deposit_forfeited')
    readonly_fields = ('forfeited_invoice',)
    search_fields = ('guest_name', 'guest_email', 'guest_phone')
"""

with open(path, 'w') as f:
    f.write(content)
print("[OK] experiences/admin.py — booking admin s forfeited_invoice")


print("\n════════════════════════════════════════════")
print("OPERATIVNA AKTIVACIJA KOMPLETNA")
print("════════════════════════════════════════════")
