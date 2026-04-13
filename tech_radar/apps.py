from django.apps import AppConfig
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

class TechRadarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tech_radar'
    verbose_name = 'Tech Radar & Capacity Monitor'
