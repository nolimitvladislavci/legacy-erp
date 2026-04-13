from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
# Automatski importaj sve adaptere da se registriraju pri startu.
from . import csv_generic  # noqa: F401
