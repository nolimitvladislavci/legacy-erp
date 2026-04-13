"""smart_import/gemini_log.py — Re-export iz models za backward compat."""
from smart_import.models import GeminiUsageLog
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
__all__ = ["GeminiUsageLog"]
