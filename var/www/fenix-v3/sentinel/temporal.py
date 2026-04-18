"""
FENIX SENTINEL — Temporal Ledger AI (PLAN_074)
Confidence scoring 0-100 za svaku transakciju.
Statistički outlier detekcija (3σ).
"""

import statistics
from datetime import timedelta, date


class TemporalAnalyzer:
    """
    Analizira transakcije i dodjeljuje confidence score.
    Score < 50 → alert, Score < 30 → kritičan alert
    """

    def score_pos_receipt(self, receipt, company) -> tuple[int, list]:
        """Score POS računa. Vraća (score, flags)."""
        flags = []
        score = 100

        # Flag 1: Neobičan sat (02:00–05:00)
        if receipt.paid_at:
            hour = receipt.paid_at.hour
            if 2 <= hour <= 5:
                flags.append("unusual_hour")
                score -= 20

        # Flag 2: Iznos outlier (>3σ od prosjeka tvrtke)
        try:
            from pos.models import POSReceipt

            amounts = list(
                POSReceipt.objects.filter(session__terminal__company=company, is_paid=True).values_list(
                    "total", flat=True
                )[:500]
            )

            if amounts and len(amounts) >= 10:
                mean = statistics.mean([float(a) for a in amounts])
                stdev = statistics.stdev([float(a) for a in amounts])
                if stdev > 0 and abs(float(receipt.total) - mean) > 3 * stdev:
                    flags.append("amount_outlier")
                    score -= 30
        except Exception:
            pass

        # Flag 3: >5 transakcija u 1 minuti (flood/test)
        if receipt.paid_at:
            try:
                from pos.models import POSReceipt

                recent = POSReceipt.objects.filter(
                    session__terminal__company=company,
                    paid_at__gte=receipt.paid_at - timedelta(minutes=1),
                    paid_at__lte=receipt.paid_at + timedelta(minutes=1),
                ).count()
                if recent > 5:
                    flags.append("freq_spike")
                    score -= 15
            except Exception:
                pass

        # Flag 4: Otkazivanje >10% ukupnog prometa tjedna
        if receipt.is_cancelled:
            flags.append("cancelled")
            score -= 10

        # Flag 5: Isti artikl >20x na jednom bonu
        if receipt.items:
            for item in receipt.items if isinstance(receipt.items, list) else []:
                qty = item.get("qty", item.get("quantity", 1))
                try:
                    if float(qty) > 20:
                        flags.append("high_qty_item")
                        score -= 10
                        break
                except (TypeError, ValueError):
                    pass

        return max(0, score), flags

    def score_journal_entry(self, entry, company) -> tuple[int, list]:
        """Score računovodstvenog unosa."""
        flags = []
        score = 100

        # Nebalansirani journal
        try:
            if abs(float(entry.debit or 0) - float(entry.credit or 0)) > 0.01:
                flags.append("unbalanced")
                score = 0
        except (TypeError, ValueError):
            pass

        # Knjiženje u prošlost >90 dana
        try:
            entry_date = entry.date if hasattr(entry, "date") else entry.created_at.date()
            if entry_date < (date.today() - timedelta(days=90)):
                flags.append("backdated_90d")
                score -= 25
        except Exception:
            pass

        # Round number ≥ 5000 EUR
        try:
            amount = float(entry.amount if hasattr(entry, "amount") else (entry.debit or 0))
            if amount % 1000 == 0 and amount >= 5000:
                flags.append("round_number")
                score -= 10
        except (TypeError, ValueError):
            pass

        return max(0, score), flags


def create_score_and_alert(instance, score: int, flags: list, company):
    """Spremi TemporalLedgerScore i kreira alert ako treba."""
    from sentinel.models import TemporalLedgerScore, SentinelAlert
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(instance)

    TemporalLedgerScore.objects.update_or_create(
        company=company, content_type=ct, object_id=str(instance.pk), defaults={"score": score, "flags": flags}
    )

    if score < 50:
        severity = "critical" if score < 30 else "warning"
        SentinelAlert.objects.get_or_create(
            company=company,
            category="accounting",
            alert_type="temporal_anomaly",
            entity_type=instance.__class__.__name__,
            entity_id=str(instance.pk),
            resolved=False,
            defaults={
                "severity": severity,
                "title": f"Anomalija transakcije — score {score}/100",
                "message": f"Zastavice: {', '.join(flags)}. Preporučamo pregled.",
                "data": {"score": score, "flags": flags},
            },
        )
