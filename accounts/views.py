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
        elif len(p1) < 8:
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
        if len(password) < 8:
            errors['password'] = 'Lozinka mora imati najmanje 8 znakova.'
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
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, 'Racun kreiran! Dobrodosli.')
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
    if not membership_id:
        messages.error(request, 'Nedostaje membership_id.')
        return redirect('/')
    try:
        mem = CompanyMembership.objects.select_related('company').get(
            pk=membership_id, user=request.user, is_active=True
        )
        request.session['active_membership_id'] = mem.id
        messages.success(request, f'Prebaceno na: {mem.company.name} ({mem.get_role_display()})')
        # B-16: Audit log za company switch
        try:
            from worktime.tracker import track
            track(request.user, 'AUTH', 'COMPANY_SWITCH',
                  ref=str(mem.company.pk),
                  detail='Switch na %s (%s)' % (mem.company.name, mem.get_role_display()),
                  company=mem.company)
        except Exception:
            pass
    except CompanyMembership.DoesNotExist:
        messages.error(request, 'Nemate pristup toj tvrtki.')
    return redirect('/')
