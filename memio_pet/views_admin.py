"""
memio_pet/views_admin.py — Superadmin dashboard za memio.pet + memio.farm

Auth: memio session (email whitelist) ILI Django staff.
Nema redirect na Django admin — vlastiti login screen.
"""
import hashlib
import functools
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils import timezone
from django.views.decorators.http import require_POST

from memio_pet.models import (
    BreederProfile, AnimalProfile, PetHealthRecord, PetOwnership,
    BreederReview, WaitlistEntry, AddAnimalToken,
)

# Admin email whitelist (SHA-256 hashevi)
_ADMIN_EMAILS = {
    hashlib.sha256(b'ivan@limit-connect.com').hexdigest(),
    hashlib.sha256(b'ivan.brtan@hotmail.com').hexdigest(),
}


def _is_memio_admin(request):
    """Provjeri je li korisnik memio admin (session ili Django staff)."""
    if request.user.is_authenticated and request.user.is_staff:
        return True
    breeder_email = request.session.get('memio_breeder_email', '')
    if breeder_email:
        h = hashlib.sha256(breeder_email.strip().lower().encode()).hexdigest()
        if h in _ADMIN_EMAILS:
            return True
    return False


def memio_admin_required(view_func):
    """Dekorator: memio admin auth — vlastiti login, ne Django admin."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if _is_memio_admin(request):
            return view_func(request, *args, **kwargs)
        # Nije admin — prikaži login
        if request.method == 'POST' and 'admin_email' in request.POST:
            email = request.POST.get('admin_email', '').strip().lower()
            h = hashlib.sha256(email.encode()).hexdigest()
            if h in _ADMIN_EMAILS:
                bp = BreederProfile.find_by_email(email)
                if bp:
                    request.session['memio_breeder_pk'] = str(bp.pk)
                    request.session['memio_breeder_email'] = email
                    request.session.set_expiry(86400 * 7)
                    return redirect(request.path)
            return render(request, 'memio_pet/admin_login.html', {
                'error': 'Nemaš pristup. Samo admin emailovi.',
            })
        return render(request, 'memio_pet/admin_login.html')
    return wrapper


@memio_admin_required
def memio_dashboard(request):
    """Glavni superadmin dashboard — pregled svega."""
    db = 'memio_pets'

    # Profili
    profiles = list(BreederProfile.objects.using(db).all().order_by('-created_at'))
    profile_types = {}
    for p in profiles:
        t = p.get_account_type_display()
        profile_types[t] = profile_types.get(t, 0) + 1

    # Životinje
    animals = list(AnimalProfile.objects.using(db).all().select_related('breeder').order_by('-created_at'))
    animal_stats = {
        'total': len(animals),
        'aktivno': sum(1 for a in animals if a.status == 'aktivno'),
        'uginulo': sum(1 for a in animals if a.status == 'uginulo'),
        'u_azilu': sum(1 for a in animals if a.status == 'u_azilu'),
    }

    # GDPR consent
    pending_consent = [p for p in profiles if p.needs_parental_consent]

    # Waitlist
    waitlist_count = WaitlistEntry.objects.using(db).count()

    # Health records
    health_count = PetHealthRecord.objects.using(db).count()

    # memio.farm
    farm_stats = _get_farm_stats()

    return render(request, 'memio_pet/admin_dashboard.html', {
        'profiles': profiles,
        'profile_types': profile_types,
        'animals': animals,
        'animal_stats': animal_stats,
        'pending_consent': pending_consent,
        'waitlist_count': waitlist_count,
        'health_count': health_count,
        'farm_stats': farm_stats,
        'now': timezone.now(),
    })


@memio_admin_required
@require_POST
def admin_animal_action(request, animal_id):
    """Brze akcije na životinjama: promijeni status, transfer, obriši."""
    db = 'memio_pets'
    import uuid
    try:
        animal = AnimalProfile.objects.using(db).get(pk=uuid.UUID(str(animal_id)))
    except AnimalProfile.DoesNotExist:
        messages.error(request, _('Životinja ne postoji.'))
        return redirect('memio_admin_dashboard')

    action = request.POST.get('action', '')

    if action == 'change_status':
        new_status = request.POST.get('new_status', '')
        if new_status in dict(AnimalProfile.STATUS_CHOICES):
            old = animal.status
            animal.status = new_status
            animal.save(using=db, update_fields=['status', 'updated_at'])
            if new_status == 'uginulo':
                from memio_pet.models import MemorialProfile
                MemorialProfile.objects.using(db).get_or_create(animal=animal)
            messages.success(request, f'{animal.name}: {old} → {new_status}')

    elif action == 'transfer':
        new_breeder_id = request.POST.get('new_breeder_id', '')
        try:
            new_breeder = BreederProfile.objects.using(db).get(pk=uuid.UUID(str(new_breeder_id)))
            animal.breeder = new_breeder
            animal.breeder_name_snapshot = new_breeder.name
            animal.save(using=db, update_fields=['breeder', 'breeder_name_snapshot', 'updated_at'])
            messages.success(request, f'{animal.name} prebačen na {new_breeder.name}')
        except BreederProfile.DoesNotExist:
            messages.error(request, _('Profil ne postoji.'))

    elif action == 'delete':
        name = animal.name
        animal.delete(using=db)
        messages.success(request, f'{name} obrisan.')

    return redirect('memio_admin_dashboard')


@memio_admin_required
@require_POST
def admin_profile_action(request, profile_id):
    """Brze akcije na profilima: verificiraj, obriši, grant consent."""
    db = 'memio_pets'
    import uuid
    try:
        bp = BreederProfile.objects.using(db).get(pk=uuid.UUID(str(profile_id)))
    except BreederProfile.DoesNotExist:
        messages.error(request, _('Profil ne postoji.'))
        return redirect('memio_admin_dashboard')

    action = request.POST.get('action', '')

    if action == 'verify':
        bp.is_cro_validated = True
        bp.validated_at = timezone.now()
        bp.validated_name = bp.name
        bp.save(using=db, update_fields=['is_cro_validated', 'validated_at', 'validated_name'])
        messages.success(request, f'{bp.name} verificiran ✓')

    elif action == 'grant_consent':
        bp.parental_consent = True
        bp.consent_given_at = timezone.now()
        bp.consent_token = ''
        bp.save(using=db, update_fields=['parental_consent', 'consent_given_at', 'consent_token'])
        messages.success(request, f'GDPR pristanak odobren za {bp.name}')

    elif action == 'delete':
        name = bp.name
        AnimalProfile.objects.using(db).filter(breeder=bp).delete()
        bp.delete(using=db)
        messages.success(request, f'Profil {name} + sve životinje obrisani.')

    return redirect('memio_admin_dashboard')


def _get_farm_stats():
    """Dohvati statistike memio.farm baze."""
    try:
        from memio_farm.models import FarmProfile, FarmAnimal, Beehive
        db = 'memio_farm'
        return {
            'farms': FarmProfile.objects.using(db).count(),
            'animals': FarmAnimal.objects.using(db).count(),
            'beehives': Beehive.objects.using(db).count(),
            'farm_list': list(FarmProfile.objects.using(db).all().order_by('-created_at')[:10]),
        }
    except DatabaseError:
        return {'farms': 0, 'animals': 0, 'beehives': 0, 'farm_list': [], 'error': 'Baza nije dostupna'}
