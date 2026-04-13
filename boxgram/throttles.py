from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class VoteRateThrottle(AnonRateThrottle):
    """Max 5 glasova po satu po IP-u."""
    scope = 'vote'


class ImportRateThrottle(UserRateThrottle):
    """Max 20 importa po satu po korisniku."""
    scope = 'import'
