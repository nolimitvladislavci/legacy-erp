from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class VoteRateThrottle(AnonRateThrottle):
    """Max 5 glasova po satu po IP-u."""
    scope = 'vote'


class ImportRateThrottle(UserRateThrottle):
    """Max 20 importa po satu po korisniku."""
    scope = 'import'
