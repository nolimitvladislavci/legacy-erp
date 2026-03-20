import os, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django; django.setup()

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
    ('/invoicing/',          'Invoice list'),
    ('/invoicing/wizard/',   'Invoice wizard'),
    ('/invoicing/form/',     'Invoice standalone form'),
    ('/invoicing/fiscal/batch/', 'Fiscal batch'),
    ('/pos/',                'POS dashboard'),
    ('/worktime/',           'Worktime worker'),
    ('/worktime/manager/',   'Worktime manager'),
    ('/projects/',           'Projects list'),
    ('/projects/1/',         'Project detail'),
    ('/projects/new/',       'Project create'),
    ('/projects/1/edit/',    'Project edit'),
    ('/appointments/lista/', 'Appointments list'),
    ('/appointments/new/',   'Appointment create'),
    ('/konto/',              'Konto index'),
    ('/konto/transactions/', 'Konto transactions'),
    ('/companies/settings/', 'Company settings'),
    ('/partners/',           'Partners list'),
    ('/burza/',              'Burza kanban'),
    ('/interventions/',      'Interventions'),
    ('/ai/',                 'AI chat'),
    ('/website/editor/',     'Website editor'),
    ('/dashboard/company/',  'Company dashboard'),
    ('/accounts/password/',  'Password change'),
]

REAL_PH = [r'TODO', r'Coming soon', r'Under construction', r'Not yet implemented',
           r'STUB', r'Lorem ipsum', r'u izradi', r'dolazi uskoro', r'nije implementiran']

def strip_html(html):
    return re.sub(r'<[^>]+>', ' ', html)

issues = []

with override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['*']):
    for url, name in pages:
        r = c.get(url, HTTP_HOST='viskovic-group.de')
        body = r.content.decode()
        text_only = strip_html(body)
        form_count = body.count('<form')
        submit_count = len(re.findall(r'type=["\']submit["\']', body))
        empty_action = len(re.findall(r'<form[^>]*action=["\']["\']', body))
        real_ph = [kw for kw in REAL_PH if re.search(kw, text_only, re.I)]
        missing_form = form_count == 0 and any(x in url for x in ['/new/', '/create/', '/form/', '/wizard/'])
        problems = []
        if real_ph: problems.append('PLACEHOLDER_TEXT:'+str(real_ph))
        if empty_action: problems.append('EMPTY_ACTION:'+str(empty_action))
        if missing_form: problems.append('NO_FORM_ON_CREATE_PAGE')
        if form_count > 0 and submit_count == 0: problems.append('FORMS_WITHOUT_SUBMIT')
        status = 'OK' if r.status_code == 200 else f'ERR{r.status_code}'
        prob_str = '  !! ' + ' | '.join(problems) if problems else ''
        if problems: issues.append((name, url, problems))
        print(f'{status}  f={form_count:2d} s={submit_count:2d}  {name}{prob_str}')

print()
print('='*60)
if issues:
    print(f'PROBLEMI ({len(issues)}):')
    for name, url, probs in issues:
        print(f'  [{name}] ({url}): {probs}')
else:
    print('Nema problema - sve forme su funkcionalne!')
