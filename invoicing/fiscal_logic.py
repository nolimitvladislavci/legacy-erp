import os

from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


def get_cert_path():
    # Profesionalni pristup: putanja se traži u settings ili default lokaciji
    base_path = getattr(settings, 'FISCAL_CERT_PATH', '/var/www/fina-connect/certs/')
    cert_name = getattr(settings, 'FISCAL_CERT_NAME', 'fina_cert.p12')
    return os.path.join(base_path, cert_name)
