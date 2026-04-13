"""
EU Audit Guard — 3 nagazne mine za EU fondove.

1. Double-Dipping detekcija — preklapanje sati istog korisnika
2. Mjesečni fond limit (Pravilo 100%) — max 176h/mjesec
3. Potpisni blok validacija — approved_by + approved_at obavezni

Poziva se PRIJE generiranja EU timesheeta i pri save() TimeEntry.
"""
import logging
from decimal import Decimal

from django.db.models import Sum

logger = logging.getLogger('eu_audit')


class EUAuditError(Exception):
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class EUAuditGuard:

    # ── MINA 1: Double-Dipping ─────────────────────────────────

    @classmethod
    def check_double_dipping(cls, user, date, start_time, end_time, exclude_pk=None):
        """Provjeri preklapanje sati za istog korisnika u istom danu."""
        from worktime.models import TimeEntry

        if not start_time or not end_time:
            return []

        qs = TimeEntry.objects.filter(
            user=user, date=date,
            start_time__isnull=False, end_time__isnull=False,
            start_time__lt=end_time, end_time__gt=start_time,
            status__in=['APPROVED', 'PENDING'],
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        conflicts = []
        for entry in qs:
            conflicts.append({
                'entry_id': entry.pk,
                'project': entry.project.code if entry.project else '?',
                'date': str(entry.date),
                'time': '%s-%s' % (entry.start_time, entry.end_time),
            })

        if conflicts:
            logger.warning('[EU AUDIT] Double-dipping: user=%s date=%s conflicts=%d', user, date, len(conflicts))
        return conflicts

    @classmethod
    def validate_no_overlap(cls, time_entry):
        """Raises EUAuditError ako postoji preklapanje."""
        conflicts = cls.check_double_dipping(
            user=time_entry.user, date=time_entry.date,
            start_time=time_entry.start_time, end_time=time_entry.end_time,
            exclude_pk=time_entry.pk if time_entry.pk else None,
        )
        if conflicts:
            raise EUAuditError(
                'DOUBLE_DIPPING',
                'Preklapanje radnog vremena! %d konflikt(a) na %s. '
                'EU revizija ne dopušta dvostruko financiranje istih sati.' % (len(conflicts), time_entry.date),
                details={'conflicts': conflicts},
            )

    # ── MINA 2: Mjesečni fond (Pravilo 100%) ──────────────────

    @classmethod
    def check_monthly_cap(cls, user, year, month, max_hours=None):
        """Provjeri mjesečni fond sati (default: radni dani × 8h)."""
        from worktime.models import TimeEntry
        import calendar
        from datetime import date

        if not max_hours:
            _, days_in_month = calendar.monthrange(year, month)
            workdays = sum(1 for d in range(1, days_in_month + 1) if date(year, month, d).weekday() < 5)
            max_hours = Decimal(str(workdays * 8))

        total = TimeEntry.objects.filter(
            user=user, date__year=year, date__month=month, status='APPROVED',
        ).aggregate(total=Sum('duration'))['total'] or Decimal('0')

        exceeded = total > max_hours
        if exceeded:
            logger.warning('[EU AUDIT] Monthly cap: user=%s %02d/%d %sh/%sh', user, month, year, total, max_hours)

        return {'total_hours': total, 'max_hours': max_hours, 'exceeded': exceeded, 'excess': max(Decimal('0'), total - max_hours)}

    @classmethod
    def validate_monthly_cap(cls, user, year, month, max_hours=None):
        """Raises EUAuditError ako prelazi fond."""
        result = cls.check_monthly_cap(user, year, month, max_hours)
        if result['exceeded']:
            raise EUAuditError(
                'MONTHLY_CAP_EXCEEDED',
                'Mjesečni fond prekoračen: %sh/%sh za %02d/%d.' % (result['total_hours'], result['max_hours'], month, year),
                details=result,
            )

    # ── MINA 3: Potpisni blok ─────────────────────────────────

    @classmethod
    def validate_signatures(cls, entries):
        """Provjeri da sve entries imaju approved_by + approved_at."""
        unsigned = []
        for entry in entries:
            if not entry.approved_by or not entry.approved_at:
                unsigned.append({
                    'entry_id': entry.pk,
                    'date': str(entry.date),
                    'missing': 'approved_by' if not entry.approved_by else 'approved_at',
                })
        if unsigned:
            logger.warning('[EU AUDIT] %d unsigned entries', len(unsigned))
        return unsigned

    @classmethod
    def validate_signatures_strict(cls, entries):
        """Raises EUAuditError za nepotpisane unose."""
        unsigned = cls.validate_signatures(entries)
        if unsigned:
            raise EUAuditError(
                'UNSIGNED_ENTRIES',
                '%d unos(a) nema potpis voditelja. EU timesheet zahtijeva potpis.' % len(unsigned),
                details={'unsigned': unsigned},
            )

    # ── KOMBINIRANI CHECK ─────────────────────────────────────

    @classmethod
    def pre_export_audit(cls, user, year, month, entries, max_hours=None):
        """Kompletna provjera PRIJE generiranja EU timesheeta."""
        for entry in entries:
            cls.validate_no_overlap(entry)
        cls.validate_monthly_cap(user, year, month, max_hours)
        cls.validate_signatures_strict(entries)
        logger.info('[EU AUDIT] Pre-export PASSED: user=%s %02d/%d', user, month, year)
