"""
Certificate Expiry Monitor — Rupa 3 zatvorena.

Provjerava sve FINA/TSE certifikate i javlja kad ističu.
Pokreće se iz Celery beat (jednom dnevno, 08:00).
Alert: POS Pulse critical event + log.
"""
import logging
import os
from datetime import datetime

from django.db import DatabaseError

logger = logging.getLogger('eracun.cert_monitor')


def check_all_certs():
    """
    Provjeri sve certifikate u sustavu.
    Returns: list of {company, cert_type, expires, days_left, status}
    """
    results = []

    # 1. FINA fiskalizacija certifikati
    try:
        from fiskalizacija.models import FiscalConfig
        for fc in FiscalConfig.objects.select_related('company').filter(is_active=True):
            cert_path = fc.cert_path
            if cert_path and os.path.exists(cert_path):
                info = _check_p12(cert_path, fc.get_password())
                if info:
                    info['company'] = fc.company.name
                    info['cert_type'] = 'FINA Fiskalizacija'
                    results.append(info)
    except OSError as e:
        logger.warning('Fiscal cert check error: %s', e)

    # 2. eRačun certifikati
    try:
        from eracun.models import ERacunConfig
        for ec in ERacunConfig.objects.select_related('company').all():
            if ec.cert_p12 and hasattr(ec.cert_p12, 'path') and os.path.exists(ec.cert_p12.path):
                info = _check_p12(ec.cert_p12.path, ec.cert_password or '')
                if info:
                    info['company'] = ec.company.name
                    info['cert_type'] = 'eRačun'
                    results.append(info)
    except OSError as e:
        logger.warning('eRacun cert check error: %s', e)

    # 3. Shared certs in /certs/ directory
    certs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'certs')
    if os.path.isdir(certs_dir):
        for f in os.listdir(certs_dir):
            if f.endswith('.p12') or f.endswith('.pfx'):
                path = os.path.join(certs_dir, f)
                info = _check_p12(path, '')
                if info:
                    info['company'] = 'Shared'
                    info['cert_type'] = f'Certifikat: {f}'
                    results.append(info)

    return results


def _check_p12(cert_path, password):
    """Extract expiry date from P12 certificate."""
    try:
        from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates

        with open(cert_path, 'rb') as f:
            p12_data = f.read()

        pwd = password.encode() if password else None
        _, cert, _ = load_key_and_certificates(p12_data, pwd)

        if cert is None:
            return None

        expires = cert.not_valid_after_utc
        # Convert to naive datetime if needed for comparison
        now = datetime.now(tz=__import__('datetime').timezone.utc)
        days_left = (expires - now).days

        status = 'ok'
        if days_left <= 0:
            status = 'EXPIRED'
        elif days_left <= 7:
            status = 'CRITICAL'
        elif days_left <= 14:
            status = 'WARNING'
        elif days_left <= 30:
            status = 'ATTENTION'

        subject = cert.subject.rfc4514_string() if cert.subject else ''

        return {
            'path': cert_path,
            'subject': subject,
            'expires': expires.isoformat(),
            'days_left': days_left,
            'status': status,
        }
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.warning('Cannot read cert %s: %s', cert_path, e)
        return {
            'path': cert_path,
            'subject': 'ERROR',
            'expires': 'N/A',
            'days_left': -1,
            'status': 'ERROR',
            'error': str(e)[:100],
        }


def run_daily_check():
    """
    Dnevna provjera — pokreće se iz Celery beat.
    Kreira POS Pulse alert za certifikate koji uskoro ističu.
    """
    results = check_all_certs()

    alerts = []
    for r in results:
        if r['status'] in ('EXPIRED', 'CRITICAL', 'WARNING', 'ATTENTION'):
            alerts.append(r)

            # POS Pulse alert
            severity = {
                'EXPIRED': 'critical',
                'CRITICAL': 'critical',
                'WARNING': 'warning',
                'ATTENTION': 'info',
            }.get(r['status'], 'info')

            try:
                from companies.models import Company
                from pos.pulse import emit
                company = Company.objects.filter(name=r['company']).first()
                if company:
                    emit(
                        company, 'alert_fiscal', severity,
                        f'Certifikat ističe za {r["days_left"]} dana!',
                        f'{r["cert_type"]} — {r["subject"][:60]} — expires {r["expires"][:10]}',
                        metadata={
                            'cert_type': r['cert_type'],
                            'days_left': r['days_left'],
                            'path': r['path'],
                        },
                    )
            except DatabaseError as e:
                logger.warning('Pulse cert alert failed: %s', e)

    if alerts:
        logger.warning('CERT ALERT: %d certificates expiring soon!', len(alerts))
        for a in alerts:
            logger.warning(
                '  [%s] %s — %s — %d days left — %s',
                a['status'], a['company'], a['cert_type'], a['days_left'], a['expires'],
            )
    else:
        logger.info('Cert check OK: %d certificates, all valid', len(results))

    return results
