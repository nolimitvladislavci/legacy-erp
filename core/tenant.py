"""
Multi-tenancy thread-local storage.

Koristi se kao:
    from core.tenant import get_current_company, set_current_company
"""

import threading

_thread_locals = threading.local()


def get_current_company():
    """Vraća aktivnu tvrtku za trenutni request thread. Može biti None."""
    return getattr(_thread_locals, "company", None)


def set_current_company(company):
    """Postavlja aktivnu tvrtku za trenutni request thread."""
    _thread_locals.company = company


def clear_current_company():
    """Briše tvrtku (poziva se na kraju requesta)."""
    _thread_locals.company = None
