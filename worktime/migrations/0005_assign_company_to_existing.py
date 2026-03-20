"""Data migration: assign existing worktime records to company via user.profile.company."""
from django.db import migrations


def assign_companies(apps, schema_editor):
    UserProfile = apps.get_model('accounts', 'UserProfile')
    Company = apps.get_model('companies', 'Company')

    # Build user->company mapping from UserProfile
    user_company = {}
    for up in UserProfile.objects.select_related('company').filter(company__isnull=False):
        user_company[up.user_id] = up.company

    # Fallback: first company
    default_company = Company.objects.first()
    if not default_company:
        print("  No companies found, skipping assignment")
        return

    def get_company(user_id):
        return user_company.get(user_id, default_company)

    # --- WorkGroup ---
    WorkGroup = apps.get_model('worktime', 'WorkGroup')
    for wg in WorkGroup.objects.filter(company__isnull=True):
        if wg.manager_id and wg.manager_id in user_company:
            wg.company = user_company[wg.manager_id]
        else:
            wg.company = default_company
        wg.save(update_fields=['company'])
    print(f"  WorkGroup: {WorkGroup.objects.count()} records assigned")

    # --- Project ---
    Project = apps.get_model('worktime', 'Project')
    for p in Project.objects.filter(company__isnull=True):
        # Try to find company from work_group or first member
        if p.work_group_id:
            try:
                wg = WorkGroup.objects.get(pk=p.work_group_id)
                p.company = wg.company
            except WorkGroup.DoesNotExist:
                p.company = default_company
        else:
            p.company = default_company
        p.save(update_fields=['company'])
    print(f"  Project: {Project.objects.count()} records assigned")

    # --- EmployeeProfile ---
    EmployeeProfile = apps.get_model('worktime', 'EmployeeProfile')
    for ep in EmployeeProfile.objects.filter(company__isnull=True):
        ep.company = get_company(ep.user_id)
        ep.save(update_fields=['company'])
    print(f"  EmployeeProfile: {EmployeeProfile.objects.count()} records assigned")

    # --- TimeEntry ---
    TimeEntry = apps.get_model('worktime', 'TimeEntry')
    for te in TimeEntry.objects.filter(company__isnull=True):
        te.company = get_company(te.user_id)
        te.save(update_fields=['company'])
    print(f"  TimeEntry: {TimeEntry.objects.count()} records assigned")

    # --- ActiveTimer ---
    ActiveTimer = apps.get_model('worktime', 'ActiveTimer')
    for at in ActiveTimer.objects.filter(company__isnull=True):
        at.company = get_company(at.user_id)
        at.save(update_fields=['company'])
    print(f"  ActiveTimer: {ActiveTimer.objects.count()} records assigned")

    # --- TimeEntryTemplate ---
    TimeEntryTemplate = apps.get_model('worktime', 'TimeEntryTemplate')
    for t in TimeEntryTemplate.objects.filter(company__isnull=True):
        t.company = get_company(t.user_id)
        t.save(update_fields=['company'])
    print(f"  TimeEntryTemplate: {TimeEntryTemplate.objects.count()} records assigned")

    # --- DailyNote ---
    DailyNote = apps.get_model('worktime', 'DailyNote')
    for dn in DailyNote.objects.filter(company__isnull=True):
        dn.company = get_company(dn.user_id)
        dn.save(update_fields=['company'])
    print(f"  DailyNote: {DailyNote.objects.count()} records assigned")

    # --- ProjectPhoto ---
    ProjectPhoto = apps.get_model('worktime', 'ProjectPhoto')
    for pp in ProjectPhoto.objects.filter(company__isnull=True):
        pp.company = get_company(pp.user_id)
        pp.save(update_fields=['company'])
    print(f"  ProjectPhoto: {ProjectPhoto.objects.count()} records assigned")


class Migration(migrations.Migration):

    dependencies = [
        ('worktime', '0004_activetimer_company_dailynote_company_and_more'),
        ('accounts', '0001_initial'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(assign_companies, migrations.RunPython.noop),
    ]
