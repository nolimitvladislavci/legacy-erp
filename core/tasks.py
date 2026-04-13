"""core/tasks.py — Centralni Celery taskovi."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  ERROR NOTIFICATION — WhatsApp + Email za trojku
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=2, soft_time_limit=30)
def notify_error_to_team(self, user, path, method, exc_class, exc_message, category, traceback, ip):
    """
    Šalje WhatsApp + email notifikaciju trojci kad se dogodi 500.

    Trojka:
      - Nikša (dev) — dobije traceback
      - Marija (ops) — dobije user-friendly poruku
      - Dev kanal — dobije puni log
    """
    import logging
    from datetime import datetime

    from django.conf import settings

    logger = logging.getLogger(__name__)

    timestamp = datetime.now().strftime("%H:%M:%S")
    date_str = datetime.now().strftime("%d.%m.%Y")

    # ── Poruka za dev (puni traceback) ──
    dev_message = (
        f"🔴 *500 ERROR* — {date_str} {timestamp}\n\n"
        f"*User:* {user}\n"
        f"*Path:* {method} {path}\n"
        f"*Exception:* {exc_class}\n"
        f"*Message:* {exc_message[:300]}\n"
        f"*Category:* {category}\n"
        f"*IP:* {ip}\n\n"
        f"```\n{traceback[-1500:]}\n```"
    )

    # ── Poruka za ops (user-friendly) ──
    ops_message = (
        f"⚠️ Greška u sustavu — {timestamp}\n\n"
        f"Korisnik *{user}* je naišao na grešku na stranici {path}.\n"
        f"Tip: {category}\n"
        f"Tim je automatski obaviješten."
    )

    # ── WhatsApp ──
    try:
        from core.whatsapp import send_text

        # Dev telefoni — iz environment varijabli
        dev_phones = getattr(settings, "ERROR_NOTIFY_PHONES", [])
        ops_phones = getattr(settings, "ERROR_NOTIFY_OPS_PHONES", [])

        for phone in dev_phones:
            try:
                send_text(phone, dev_message)
                logger.info("Error WhatsApp sent to dev: %s", phone)
            except Exception as e:
                logger.warning("WhatsApp dev notify failed for %s: %s", phone, e)

        for phone in ops_phones:
            try:
                send_text(phone, ops_message)
                logger.info("Error WhatsApp sent to ops: %s", phone)
            except Exception as e:
                logger.warning("WhatsApp ops notify failed for %s: %s", phone, e)

    except ImportError:
        logger.warning("WhatsApp module not available for error notification")

    # ── Email fallback ──
    try:
        from django.core.mail import mail_admins

        mail_admins(
            subject=f"[500] {exc_class} at {path}",
            message=f"User: {user}\nPath: {method} {path}\n"
            f"Exception: {exc_class}: {exc_message}\n"
            f"Category: {category}\nIP: {ip}\n\n"
            f"Traceback:\n{traceback}",
            fail_silently=True,
        )
    except ImportError as e:
        logger.warning("Email error notification failed: %s", e)


@shared_task(name="core.run_system_test_task", bind=True, max_retries=0)
def run_system_test_task(self, phone="+491723006985", quick=False):
    """
    Autonomni test sustava — pokreće se iz Celery beat.
    Testira sve module i šalje WhatsApp report Ivanu.
    """
    import logging

    logger = logging.getLogger("system_test")
    logger.info(f"🤖 run_system_test_task pokrenut — phone={phone}")

    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    try:
        call_command("run_system_test", notify=phone, quick=quick, stdout=out)
    except Exception as e:
        logger.error(f"run_system_test crash: {e}")
        try:
            from core.whatsapp import send_text

            send_text(phone=phone, message=f"🔴 FENIX TEST CRASH\n{type(e).__name__}: {e}", session="default")
        except ImportError:
            logger.exception("Failed to import send_text")
    return out.getvalue()


@shared_task(name="core.sonnet_cycle", bind=True, max_retries=2)
def sonnet_cycle(self):
    """
    Sonnet vođa projekta — poziva se svaka 2 sata.
    Čita FENIX_STATUS + git log, odlučuje što dalje,
    pokreće Gemini taskove, javlja Ivanu ako treba.
    """
    try:
        from core.sonnet_agent import run_sonnet_cycle

        run_sonnet_cycle()
    except ImportError as exc:
        import logging

        logging.getLogger("sonnet_agent").error(f"sonnet_cycle crash: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name="core.ai_health_check", bind=True, max_retries=0)
def ai_health_check(self):
    """
    AI Infrastruktura Health Check — svaki sat.
    Provjeri Gemini, Haiku, Sonnet, WAHA, Celery, Redis.
    Ako nešto pukne — WhatsApp Ivan + automatski restart gdje moguće.
    """
    try:
        from core.ai_health import run_ai_health_check

        return run_ai_health_check()
    except ImportError as e:
        import logging

        logging.getLogger("ai_health").error(f"Health check crash: {e}")


@shared_task(name="core.database_backup", bind=True, max_retries=2, soft_time_limit=300)
def database_backup(self):
    """
    Dnevni backup PostgreSQL baze — svaki dan u 02:00.

    Workflow:
    1. pg_dump → komprimirani .dump fajl u /var/backups/fina-erp/
    2. Čuva zadnjih 7 dana (stari se brišu)
    3. Verifikacija integriteta (pg_restore --list)
    4. WhatsApp Ivan: OK ili ALARM

    DB: fina_erp (127.0.0.1:5432)
    Auth: /root/.pgpass (600 permissions)
    Format: custom (-F c) — najbrži restore, kompresija ~10:1
    """
    import glob
    import os
    import subprocess
    from datetime import datetime

    log = logging.getLogger("core.backup")

    BACKUP_DIR = "/var/backups/fina-erp"
    KEEP_DAYS = 7
    DB_NAME = "fina_erp"
    DB_USER = "viskovic_user"
    DB_HOST = "127.0.0.1"
    DB_PORT = "5432"
    IVAN_PHONE = "+4915771998747"

    os.makedirs(BACKUP_DIR, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{BACKUP_DIR}/{DB_NAME}_{ts}.dump"

    # ── 1. pg_dump ─────────────────────────────────────────
    try:
        result = subprocess.run(
            ["pg_dump", "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER, "-d", DB_NAME, "-F", "c", "-f", backup_file],
            capture_output=True,
            text=True,
            timeout=240,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr[:300]}")

        size_mb = round(os.path.getsize(backup_file) / 1024 / 1024, 1)
        if size_mb < 1:
            raise RuntimeError(f"Backup presitan: {size_mb}MB — vjerojatno prazan dump")

        log.info(f"Backup OK: {backup_file} ({size_mb}MB)")

    except OSError as e:
        log.error(f"Backup FAILED: {e}")
        _backup_whatsapp(IVAN_PHONE, f"🔴 BACKUP ALARM\n{DB_NAME}: {e}")
        raise self.retry(exc=e, countdown=600)

    # ── 2. Verifikacija integriteta ──────────────────────────
    try:
        verify = subprocess.run(
            ["pg_restore", "-h", DB_HOST, "-U", DB_USER, "--list", backup_file],
            capture_output=True,
            text=True,
            timeout=30,
        )
        section_count = len(verify.stdout.strip().split("\n"))
        if section_count < 100:
            raise RuntimeError(f"Sumnjivo malo sekcija u dumpu: {section_count}")
        log.info(f"Integritet OK: {section_count} sekcija")

    except (ValueError, AttributeError) as e:
        log.warning(f"Verifikacija upozorenje: {e}")
        # Ne failamo — backup postoji, samo verifikacija sumnjiva

    # ── 3. Rotacija — čuvaj zadnjih KEEP_DAYS dana ──────────
    all_dumps = sorted(glob.glob(f"{BACKUP_DIR}/{DB_NAME}_*.dump"))
    deleted = 0
    while len(all_dumps) > KEEP_DAYS:
        old = all_dumps.pop(0)
        try:
            os.remove(old)
            deleted += 1
            log.info(f"Obrisan stari backup: {old}")
        except OSError as e:
            log.warning(f"Ne mogu obrisati {old}: {e}")

    # ── 4. WhatsApp potvrda ──────────────────────────────────
    msg = (
        f"✅ Backup OK — {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"Baza: {DB_NAME} · Veličina: {size_mb}MB\n"
        f"Fajl: {os.path.basename(backup_file)}\n"
        f"Čuvanih backupa: {len(all_dumps)} · Obrisano starih: {deleted}"
    )
    _backup_whatsapp(IVAN_PHONE, msg)

    return {
        "status": "ok",
        "file": backup_file,
        "size_mb": size_mb,
        "sections": section_count if "section_count" in dir() else 0,
        "deleted_old": deleted,
    }


def _backup_whatsapp(phone, message):
    """Helper — pošalji WhatsApp, tiho ako padne."""
    try:
        from core.whatsapp import send_text

        send_text(phone=phone, message=message)
    except ImportError as e:
        logging.getLogger("core.backup").warning(f"WhatsApp backup notif failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  SUBSCRIPTION TRACKER — Podsjetnici za pretplate i račune
# ═══════════════════════════════════════════════════════════════


@shared_task(name="core.check_subscriptions", bind=True, max_retries=1, soft_time_limit=30)
def check_subscriptions(self):
    """
    Dnevna provjera pretplata — šalje WhatsApp podsjetnike Ivanu.
    Pokreće se svaki dan u 09:00 preko Celery beat-a.
    """
    from datetime import date

    from core.notify import notify

    SUBSCRIPTIONS = [
        {
            "name": "Claude Max (Nikša)",
            "renewal_date": date(2026, 4, 27),
            "remind_days_before": [7, 3, 1, 0],
            "action": "Produžiti Max paket prije isteka",
        },
        {
            "name": "Hetzner server (Marija)",
            "renewal_date": date(2026, 5, 1),
            "remind_days_before": [7, 3, 1, 0],
            "action": "Marija treba uplatiti server",
        },
        {
            "name": "Claude Pro (Kruljac)",
            "renewal_date": date(2026, 4, 27),
            "remind_days_before": [7, 3, 1, 0],
            "action": "Kruljac treba produžiti Pro paket",
        },
    ]

    today = date.today()
    alerts = []

    for sub in SUBSCRIPTIONS:
        days_left = (sub["renewal_date"] - today).days

        if days_left < 0:
            alerts.append(f"🔴 *{sub['name']}* — ISTEKLO prije {abs(days_left)} dana!\n   ➜ {sub['action']}")
        elif days_left == 0:
            alerts.append(f"🔴 *{sub['name']}* — ISTIČE DANAS!\n   ➜ {sub['action']}")
        elif days_left in sub["remind_days_before"]:
            alerts.append(
                f"🟡 *{sub['name']}* — još {days_left} dana (istječe {sub['renewal_date'].strftime('%d.%m.')})\n"
                f"   ➜ {sub['action']}"
            )

    if alerts:
        msg = "📋 *Podsjetnik — pretplate i računi*\n\n" + "\n\n".join(alerts)
        notify("ACTION", msg, urgent=False)
        return f"Poslano {len(alerts)} podsjetnika"
    return "Nema podsjetnika za danas"
