from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

path = '/var/www/fina-connect/core/views.py'
with open(path, 'r') as f:
    content = f.read()

# Zamjena pogrešnog ključa duration_hours sa duration
content = content.replace('duration_hours', 'duration')

with open(path, 'w') as f:
    f.write(content)
