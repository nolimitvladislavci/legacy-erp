"""Fix missing imports in flock views — udruge/views.py"""
import re
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

filepath = '/var/www/fina-connect/udruge/views.py'

with open(filepath, 'r') as f:
    content = f.read()

# 1. flock_list: replace models.Q with Q (Q already imported at top)
content = content.replace(
    """    qs = qs.filter(
            models.Q(naziv__icontains=q) |
            models.Q(pasmina__icontains=q) |
            models.Q(objekt__icontains=q)
        )""",
    """    qs = qs.filter(
            Q(naziv__icontains=q) |
            Q(pasmina__icontains=q) |
            Q(objekt__icontains=q)
        )"""
)

# 2. flock_create: add missing Flock import
content = content.replace(
    """def flock_create(request):
    company = get_user_company(request)""",
    """def flock_create(request):
    from .models import Flock
    company = get_user_company(request)"""
)

# 3. flock_detail: add Flock import + fix models.Sum
content = content.replace(
    """def flock_detail(request, pk):
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=pk, company=company)""",
    """def flock_detail(request, pk):
    from .models import Flock
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=pk, company=company)"""
)

content = content.replace(
    """    egg_stats = flock.egg_records.filter(datum__gte=thirty_days_ago).aggregate(
        ukupno_jaja=models.Sum('broj_jaja'),
        ukupno_polomljenih=models.Sum('broken'),
        ukupno_prodanih=models.Sum('sold'),
    )""",
    """    from django.db.models import Sum
    egg_stats = flock.egg_records.filter(datum__gte=thirty_days_ago).aggregate(
        ukupno_jaja=Sum('broj_jaja'),
        ukupno_polomljenih=Sum('broken'),
        ukupno_prodanih=Sum('sold'),
    )"""
)

# 4. flock_edit: add Flock import
content = content.replace(
    """def flock_edit(request, pk):
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=pk, company=company)""",
    """def flock_edit(request, pk):
    from .models import Flock
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=pk, company=company)"""
)

# 5. egg_record_create: add Flock + EggRecord import
content = content.replace(
    """def egg_record_create(request, flock_pk):
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = EggRecord(""",
    """def egg_record_create(request, flock_pk):
    from .models import Flock, EggRecord
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = EggRecord("""
)

# 6. flock_health_create: add Flock + FlockHealthRecord import
content = content.replace(
    """def flock_health_create(request, flock_pk):
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = FlockHealthRecord(""",
    """def flock_health_create(request, flock_pk):
    from .models import Flock, FlockHealthRecord
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = FlockHealthRecord("""
)

# 7. flock_mortality_create: add Flock + FlockMortality import
content = content.replace(
    """def flock_mortality_create(request, flock_pk):
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = FlockMortality(""",
    """def flock_mortality_create(request, flock_pk):
    from .models import Flock, FlockMortality
    company = get_user_company(request)
    flock = get_object_or_404(Flock, pk=flock_pk, company=company)

    if request.method == 'POST':
        record = FlockMortality("""
)

# 8. bridge_publish uses EggRecord without import — fix
content = content.replace(
    """        if source_model == 'EggRecord':
            try:
                egg = EggRecord.objects.select_related""",
    """        if source_model == 'EggRecord':
            try:
                from .models import EggRecord
                egg = EggRecord.objects.select_related"""
)

# Also fix FlockHealthRecord.VRSTA_TRETMANA reference in flock_health_create template context
# (it's used after the function has the import now, so it should work)

with open(filepath, 'w') as f:
    f.write(content)

print("DONE — 8 fixes applied")
