"""
FENIX SENTINEL — Celery Beat schedule definition
Importira se iz config/settings.py
"""

SENTINEL_BEAT_SCHEDULE = {
    # Svakih 15 min — stale POS sesije (Ana's problem)
    "sentinel-stale-pos-sessions": {
        "task": "sentinel.check_stale_pos_sessions",
        "schedule": 900,  # 15 minuta
        "options": {"queue": "scheduled"},
    },
    # Svaki dan 03:00 — temporal ledger scoring
    "sentinel-temporal-ledger": {
        "task": "sentinel.temporal_ledger_score",
        "schedule": 86400,
        "options": {"queue": "scheduled"},
    },
    # Svaki dan 04:00 — audit chain verify
    "sentinel-audit-chain": {
        "task": "sentinel.audit_chain_verify",
        "schedule": 86400,
        "options": {"queue": "scheduled"},
    },
    # Svaki ponedjeljak 05:00 — fiscal compliance
    "sentinel-fiscal-scan": {
        "task": "sentinel.fiscal_compliance_scan",
        "schedule": 7 * 86400,
        "options": {"queue": "scheduled"},
    },
    # Svaki ponedjeljak 06:00 — EU navigator
    "sentinel-eu-navigator": {
        "task": "sentinel.eu_navigator_scan",
        "schedule": 7 * 86400,
        "options": {"queue": "scheduled"},
    },
    # Svaki dan 08:00 — obrasci reminder
    "sentinel-obrasci-reminder": {
        "task": "sentinel.obrasci_reminder",
        "schedule": 86400,
        "options": {"queue": "scheduled"},
    },
    # Svake nedjelje 22:00 — kalendar obveza
    "sentinel-calendar": {
        "task": "sentinel.generate_calendar",
        "schedule": 7 * 86400,
        "options": {"queue": "scheduled"},
    },
}
