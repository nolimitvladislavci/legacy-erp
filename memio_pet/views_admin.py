"""
memio_pet/views_admin.py — Superadmin dashboard za memio.pet + memio.farm

Samo za staff korisnike. Centralno upravljanje:
- Profili (korisnici, krematoriji, azili)
- Životinje (CRUD, status, transfer)
- GDPR consent pregled
- memio.farm farme + košnice
- Statistike + brze akcije
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from memio_pet.models import (
    BreederProfile, AnimalProfile, PetHealthRecord, PetOwnership,
    BreederReview, WaitlistEntry, AddAnimalToken,
)


@staff_member_required
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


@staff_member_required
@require_POST
def admin_animal_action(request, animal_id):
    """Brze akcije na životinjama: promijeni status, transfer, obriši."""
    db = 'memio_pets'
    import uuid
    try:
        animal = AnimalProfile.objects.using(db).get(pk=uuid.UUID(str(animal_id)))
    except AnimalProfile.DoesNotExist:
        messages.error(request, 'Životinja ne postoji.')
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
            messages.error(request, 'Profil ne postoji.')

    elif action == 'delete':
        name = animal.name
        animal.delete(using=db)
        messages.success(request, f'{name} obrisan.')

    return redirect('memio_admin_dashboard')


@staff_member_required
@require_POST
def admin_profile_action(request, profile_id):
    """Brze akcije na profilima: verificiraj, obriši, grant consent."""
    db = 'memio_pets'
    import uuid
    try:
        bp = BreederProfile.objects.using(db).get(pk=uuid.UUID(str(profile_id)))
    except BreederProfile.DoesNotExist:
        messages.error(request, 'Profil ne postoji.')
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
    except Exception:
        return {'farms': 0, 'animals': 0, 'beehives': 0, 'farm_list': [], 'error': 'Baza nije dostupna'}
