from core.models import BookingSignature
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from .models import UserProfile
from core.company_utils import get_user_company


class UserListView(ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        user = self.request.user
        # Superadmin vidi sve
        if user.is_superuser:
            return User.objects.select_related('profile', 'profile__company').order_by('-last_login')
        # Ostali vide samo korisnike svoje firme
        company = get_user_company(self.request)
        if not company:
            return User.objects.none()
        company_user_ids = UserProfile.objects.filter(
            company=company
        ).values_list('user_id', flat=True)
        return User.objects.filter(
            id__in=company_user_ids
        ).select_related('profile', 'profile__company').order_by('-last_login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user_company'] = get_user_company(self.request)
        return ctx

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_edit(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        # 1. Ažuriranje standardnih Django polja
        target_user.username = request.POST.get('username', target_user.username)
        target_user.first_name = request.POST.get('first_name', target_user.first_name)
        target_user.last_name = request.POST.get('last_name', target_user.last_name)
        target_user.email = request.POST.get('email', target_user.email)
        target_user.is_active = request.POST.get('is_active') == 'on'

        # 2. Promjena lozinke ako je upisana
        password = request.POST.get('password')
        if password:
            target_user.set_password(password)
            # Auto-notify via WhatsApp/email
            try:
                from accounts.password_notify import notify_password_change
                notify_password_change(target_user, password, changed_by=request.user)
            except Exception:
                pass

        # 3. Ažuriranje Uloge i automatsko mapiranje privilegija
        new_role = request.POST.get('role', 'worker')
        profile, _ = UserProfile.objects.get_or_create(user=target_user)
        profile.role = new_role
        profile.save()

        if new_role == 'superadmin':
            target_user.is_superuser = True
            target_user.is_staff = True
        elif new_role in ['company_admin', 'project_manager']:
            target_user.is_superuser = False
            target_user.is_staff = True
        else:
            target_user.is_superuser = False
            target_user.is_staff = False

        target_user.save()
        messages.success(request, f'Korisnik {target_user.username} je uspješno ažuriran s ulogom {profile.get_role_display()}.')
        return redirect('accounts:user_list')

    return render(request, 'accounts/user_form.html', {'target_user': target_user})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def reset_password_request(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    form = PasswordResetForm({'email': target_user.email})
    if form.is_valid():
        form.save(request=request, use_https=request.is_secure())
        messages.success(request, f'Reset lozinke poslan na {target_user.email}')
    return redirect('accounts:user_list')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def toggle_user_status(request, pk):
    u = get_object_or_404(User, pk=pk)
    u.is_active = not u.is_active
    u.save()
    return redirect('accounts:user_list')



@login_required
@user_passes_test(lambda u: u.is_superuser)
def translation_manager(request, lang_code='de'):
    import os

    import polib
    from django.conf import settings

    po_path = os.path.join(settings.BASE_DIR, 'locale', lang_code, 'LC_MESSAGES', 'django.po')

    if not os.path.exists(po_path):
        messages.warning(request, f'Pojmovi su u bazi već na Hrvatskom. Preusmjereno na Njemački rječnik.')
        return redirect('accounts:translation_manager', lang_code='de')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'scan':
            os.system(f"cd {settings.BASE_DIR} && {settings.BASE_DIR}/venv/bin/python manage.py makemessages -l {lang_code} -e html,py --no-wrap")
            messages.success(request, f'✅ Portal skeniran. Baza riječi za {lang_code.upper()} je ažurirana.')
            return redirect('accounts:translation_manager', lang_code=lang_code)

        elif action == 'auto_translate_module':
            target_module = request.POST.get('target_module', 'ALL')
            try:
                from deep_translator import GoogleTranslator
                po = polib.pofile(po_path)
                translator = GoogleTranslator(source='hr', target=lang_code)
                count = 0
                for entry in po:
                    if not entry.msgstr and entry.msgid:
                        # Ako prevodimo specifični modul, preskoči riječi iz drugih modula
                        if target_module != 'ALL':
                            belongs = False
                            for occ in entry.occurrences:
                                path = occ[0].replace('\\', '/')
                                if path.startswith(target_module + '/'):
                                    belongs = True
                                    break
                            if not belongs:
                                continue

                        try:
                            entry.msgstr = translator.translate(entry.msgid)
                            count += 1
                        except Exception:
                            pass
                po.save()
                os.system(f"cd {settings.BASE_DIR} && {settings.BASE_DIR}/venv/bin/python manage.py compilemessages")
                if target_module == 'ALL':
                    messages.success(request, f'✨ Uspješno prevedeno {count} pojmova u cijelom sustavu.')
                else:
                    messages.success(request, f'✨ Uspješno prevedeno {count} pojmova u modulu: {target_module.upper()}.')
            except Exception as e:
                messages.error(request, f'Greška: {str(e)}')
            return redirect('accounts:translation_manager', lang_code=lang_code)

        else:
            msgid = request.POST.get('msgid')
            msgstr = request.POST.get('msgstr')
            if msgid:
                po = polib.pofile(po_path)
                entry = po.find(msgid)
                if entry:
                    entry.msgstr = msgstr
                    po.save()
                    os.system(f"cd {settings.BASE_DIR} && {settings.BASE_DIR}/venv/bin/python manage.py compilemessages")
                    messages.success(request, f'Prijevod za "{msgid}" spremljen.')
            return redirect('accounts:translation_manager', lang_code=lang_code)

    po = polib.pofile(po_path)
    entries = []
    modules_set = set()

    for e in po:
        if e.msgid:
            # Utvrđivanje modula iz putanje datoteke
            mod_name = 'ostalo'
            if e.occurrences:
                path = e.occurrences[0][0].replace('\\', '/')
                mod_name = path.split('/')[0]
            e.module_name = mod_name
            modules_set.add(mod_name)
            entries.append(e)

    return render(request, 'accounts/translation_manager.html', {
        'entries': entries,
        'modules': sorted(list(modules_set)),
        'lang_code': lang_code,
        'languages': ['de', 'en']
    })


@login_required
def change_password(request):
    """One canonical place to change password — no old password required."""
    if request.method == 'POST':
        p1 = request.POST.get('new_password1', '').strip()
        p2 = request.POST.get('new_password2', '').strip()
        if p1 != p2:
            messages.error(request, 'Lozinke se ne podudaraju.')
        elif len(p1) < 10:
            messages.error(request, 'Lozinka mora imati najmanje 8 znakova.')
        else:
            request.user.set_password(p1)
            request.user.save()
            # Čisti must_change_password i zadrži sesiju aktivnom
            try:
                prof = request.user.profile
                if prof.must_change_password:
                    prof.must_change_password = False
                    prof.save(update_fields=['must_change_password'])
            except Exception:
                pass
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, '✓ Lozinka uspješno promijenjena.')
            return redirect('/')
    return render(request, 'accounts/change_password.html', {})


def quick_register(request):
    """Quick registration for clients (no company needed)."""
    from django.contrib.auth import login
    next_url = request.GET.get('next', request.POST.get('next', '/dashboard/'))
    company_slug = request.GET.get('company', request.POST.get('company', ''))

    if request.user.is_authenticated:
        return redirect(next_url)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        errors = {}
        if not name:
            errors['name'] = 'Ime je obavezno.'
        if not email:
            errors['email'] = 'Email je obavezan.'
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'Korisnik s ovim emailom vec postoji.'
        if len(password) < 10:
            errors['password'] = 'Lozinka mora imati najmanje 10 znakova.'
        if errors:
            return render(request, 'accounts/quick_register.html', {
                'errors': errors, 'name': name, 'email': email, 'phone': phone,
                'next': next_url, 'company': company_slug,
            })

        name_parts = name.strip().split(None, 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        base_un = email.split('@')[0].lower().replace('.', '_')[:30]
        username = base_un
        counter = 1
        while User.objects.filter(username=username).exists():
            username = '{}{}'.format(base_un, counter)
            counter += 1
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )
        # Link to company if slug provided
        if company_slug:
            try:
                from companies.models import Company
                company = Company.objects.get(slug=company_slug)
                profile, _ = UserProfile.objects.get_or_create(user=user, defaults={
                    'company': company, 'role': 'client',
                })
            except Exception:
                pass
        request.session.flush()
        login(request, user, backend='core.auth_backends.EmailOrUsernameBackend')

        # Email verifikacija (async, ne blokira)
        try:
            from accounts.email_verification import send_verification_email
            send_verification_email(user)
        except Exception:
            pass

        # Audit log
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                user=user,
                model_name='auth.User',
                object_id=str(user.pk),
                action='register',
                changes={'email': email, 'method': 'quick_register'},
                ip_address=request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', ''),
            )
        except Exception:
            pass

        messages.success(request, 'Račun kreiran! Provjerite email za verifikaciju.')
        return redirect(next_url)

    return render(request, 'accounts/quick_register.html', {
        'next': next_url, 'company': company_slug,
        'errors': {}, 'name': '', 'email': '', 'phone': '',
    })


@login_required
@require_POST
def switch_company(request):
    from accounts.models import CompanyMembership
    membership_id = request.POST.get('membership_id')
    company_id = request.POST.get('company_id')

    if not membership_id and not company_id:
        messages.error(request, 'Nedostaje membership_id ili company_id.')
        return redirect('/')

    try:
        if membership_id:
            mem = CompanyMembership.objects.select_related('company').get(
                pk=membership_id, user=request.user, is_active=True
            )
            request.session['active_membership_id'] = mem.id
            company = mem.company
            role_display = mem.get_role_display()
        elif company_id and request.user.is_superuser:
            # Superadmin pristup — filter first to avoid IntegrityError
            from companies.models import Company
            company = Company.objects.get(pk=company_id)
            mem = CompanyMembership.objects.filter(
                user=request.user, company=company
            ).first()
            if mem:
                if not mem.is_active:
                    mem.is_active = True
                    mem.save(update_fields=['is_active'])
            else:
                mem = CompanyMembership.objects.create(
                    user=request.user, company=company,
                    role='owner', is_active=True
                )
                messages.info(request, f'Pristup kreiran za: {company.name}')
            request.session['active_membership_id'] = mem.id
            role_display = 'Superadmin'
        elif company_id:
            # Umbrella admin pristup — auto-create membership za umbrella children
            from companies.models import Company
            company = Company.objects.get(pk=company_id)
            user_co = request.user.profile.company
            if user_co and user_co.is_umbrella and company.umbrella_parent_id == user_co.id:
                mem, created = CompanyMembership.objects.get_or_create(
                    user=request.user, company=company,
                    defaults={'role': 'company_admin', 'is_active': True}
                )
                request.session['active_membership_id'] = mem.id
                role_display = 'Umbrella Admin'
            else:
                messages.error(request, 'Nemate pristup toj tvrtki.')
                return redirect('/')
        else:
            messages.error(request, 'Nemate pristup toj tvrtki.')
            return redirect('/')

        # Postavi session za get_user_company
        request.session['superadmin_as_company'] = str(company.pk)
        messages.success(request, f'Prebaceno na: {company.name} ({role_display})')
        # B-16: Audit log za company switch
        try:
            from worktime.tracker import track
            track(request.user, 'AUTH', 'COMPANY_SWITCH',
                  ref=str(company.pk),
                  detail='Switch na %s (%s)' % (company.name, role_display),
                  company=company)
        except Exception:
            pass
        try:
            BookingSignature.log(request, "switch", target_model="Company", target_id=str(company.pk), target_repr=f"Switch na {company.name}")
        except Exception:
            pass
    except (CompanyMembership.DoesNotExist, Company.DoesNotExist):
        messages.error(request, 'Nemate pristup toj tvrtki.')
    return redirect('/')


# ════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
# ODABERI KOMITENTE — s AI preporukama
# ════════════════════════════════════════════════════════════

@login_required
def odaberi_komitente(request):
    """
    Svaka radnica vidi SAMO svoje komitente i slobodne (neraspoređene).
    Tuđe komitente ne vidi — privatnost i izolacija po radnici.

    Logika:
      - MOJE: firme gdje JA imam aktivni membership → prikazane, mogu maknuti
      - SLOBODNE: firme iz Konjik partnerstva koje nitko nema → mogu uzeti
      - TUĐE: firme koje ima netko drugi → NEVIDLJIVE
    """
    import uuid as _uuid
    from companies.models import Company, CompanyPartnership
    from accounts.models import CompanyMembership

    # Moje firme
    my_memberships = set(
        CompanyMembership.objects.filter(
            user=request.user, is_active=True
        ).values_list('company_id', flat=True)
    )

    # Pronađi Konjik-partnerstvo (firma u kojoj ova osoba radi)
    partner_ids = set()
    recommendation_source = ''
    for mem in CompanyMembership.objects.filter(
        user=request.user, is_active=True
    ).select_related('company'):
        managed = CompanyPartnership.objects.filter(
            partner_company=mem.company,
            valid_until__isnull=True,
        ).values_list('managed_company_id', flat=True)
        if managed:
            partner_ids.update(managed)
            recommendation_source = mem.company.name

    # Sve firme koje NETKO DRUGI već ima (iz Konjik partnerstva)
    tudje_ids = set(
        CompanyMembership.objects.filter(
            company_id__in=partner_ids,
            is_active=True,
        ).exclude(user=request.user).values_list('company_id', flat=True)
    )

    # Vidljive firme = moje + slobodne (iz Konjik partnerstva, bez tuđih)
    vidljive_ids = (partner_ids - tudje_ids) | my_memberships

    # Ako superadmin — vidi sve
    if request.user.is_superuser:
        vidljive_ids = set(Company.objects.values_list('id', flat=True))
        partner_ids = vidljive_ids

    firme = list(
        Company.objects.filter(id__in=vidljive_ids).order_by('name')
    )

    # Sortiraj: moje na vrh, pa slobodne
    moje = [c for c in firme if c.id in my_memberships]
    slobodne = [c for c in firme if c.id not in my_memberships]

    if request.method == 'POST':
        selected_ids = set()
        for cid in request.POST.getlist('company_ids'):
            try:
                selected_ids.add(_uuid.UUID(cid) if '-' in str(cid) else int(cid))
            except (ValueError, TypeError):
                selected_ids.add(cid)

        # Sigurnosna provjera: ne može uzeti tuđe
        selected_ids = selected_ids & vidljive_ids

        added = 0
        for cid in selected_ids - my_memberships:
            company = Company.objects.filter(pk=cid).first()
            if company:
                CompanyMembership.objects.get_or_create(
                    user=request.user,
                    company=company,
                    defaults={
                        'role': 'company_admin',
                        'is_active': True,
                        'is_default': not my_memberships and added == 0,
                    }
                )
                added += 1

        removed = 0
        for cid in my_memberships - selected_ids:
            updated = CompanyMembership.objects.filter(
                user=request.user, company_id=cid, is_active=True
            ).update(is_active=False)
            removed += updated

        from django.contrib import messages
        messages.success(request,
            'Odabir spremljen: %d dodano, %d uklonjeno. Ukupno: %d firmi.' % (
                added, removed, len(selected_ids)))
        return redirect('accounts:odaberi_komitente')

    return render(request, 'accounts/odaberi_komitente.html', {
        'recommended': slobodne,          # slobodne = preporučene za uzimanje
        'others': [],                      # nema "ostalih" — tuđe su skrivene
        'companies': moje + slobodne,
        'my_ids': my_memberships,
        'moje_count': len(moje),
        'slobodne_count': len(slobodne),
        'tudje_count': len(tudje_ids),
        'recommended_ids': partner_ids - tudje_ids,
        'recommendation_source': recommendation_source,
    })


@login_required
def switch_company_get(request, company_id):
    """GET-based company switch — radi bez forme/CSRF. Za mobilne browsere."""
    from accounts.models import CompanyMembership
    from companies.models import Company

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        messages.error(request, 'Firma ne postoji.')
        return redirect('/')

    if not request.user.is_superuser:
        mem = CompanyMembership.objects.filter(
            user=request.user, company=company, is_active=True
        ).first()
        if not mem:
            messages.error(request, 'Nemate pristup toj firmi.')
            return redirect('/')

    # Superadmin ili ima membership — switch
    try:
        mem = CompanyMembership.objects.filter(
            user=request.user, company=company
        ).first()
        if mem:
            if not mem.is_active:
                mem.is_active = True
                mem.save(update_fields=['is_active'])
        else:
            mem = CompanyMembership.objects.create(
                user=request.user, company=company,
                role='owner', is_active=True
            )
    except Exception:
        mem = CompanyMembership.objects.filter(
            user=request.user, company=company
        ).first()
        if not mem:
            messages.error(request, 'Greska pri prebacivanju.')
            return redirect('/')
    request.session['active_membership_id'] = mem.id
    request.session['superadmin_as_company'] = str(company.pk)
    messages.success(request, 'Prebaceno na: %s' % company.name)
    return redirect('/')
