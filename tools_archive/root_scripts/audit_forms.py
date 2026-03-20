import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from companies.models import Company
from django.test.utils import override_settings

c = Client()
u = User.objects.filter(is_superuser=True).first()
c.force_login(u)
s = c.session
comp = Company.objects.first()
s['impersonated_company_id'] = str(comp.pk)
s['impersonation_started_at'] = 0
s.save()

pages = [
    ('/invoicing/',         'Invoice list'),
    ('/invoicing/wizard/',  'Invoice wizard'),
    ('/invoicing/form/',    'Invoice standalone form'),
    ('/invoicing/fiscal/batch/', 'Fiscal batch'),
    ('/pos/',               'POS dashboard'),
    ('/worktime/',          'Worktime worker'),
    ('/worktime/manager/',  'Worktime manager'),
    ('/projects/',          'Projects list'),
    ('/projects/1/',        'Project detail'),
    ('/projects/new/',      'Project create'),
    ('/projects/1/edit/',   'Project edit'),
    ('/appointments/lista/', 'Appointments list'),
    ('/appointments/new/',  'Appointment create'),
    ('/konto/',             'Konto index'),
    ('/konto/transactions/', 'Konto transactions'),
    ('/companies/settings/', 'Company settings'),
    ('/partners/',          'Partners list'),
    ('/burza/',             'Burza kanban'),
    ('/interventions/',     'Interventions'),
    ('/ai/',                'AI chat'),
    ('/website/editor/',    'Website editor'),
    ('/dashboard/company/', 'Company dashboard'),
]

PLACEHOLDER_KW = ['TODO', 'Coming soon', 'Under construction', 'Placeholder',
                  'Not yet implemented', 'STUB', 'Lorem ipsum',
                  'u izradi', 'dolazi uskoro', 'nije implementir']

with override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['*']):
    for url, name in pages:
        r = c.get(url, HTTP_HOST='viskovic-group.de')
        body = r.content.decode()
        found_ph = [kw for kw in PLACEHOLDER_KW if kw.lower() in body.lower()]
        form_count = body.count('<form')
        submit_count = body.count('type="submit"') + body.count("type='submit'")
        # Check for action="" (empty form action = potential issue)
        empty_action = 'action=""' in body or "action=''" in body
        status_icon = '✓' if r.status_code == 200 else f'!{r.status_code}'
        ph_str = f' ⚠ PLACEHOLDER:{found_ph}' if found_ph else ''
        ea_str = ' (action="" OK)' if empty_action else ''
        print(f'{status_icon} forms={form_count} submit={submit_count}{ea_str}{ph_str}  |  {name}')
