"""
konto/tasks_vat.py
Monthly VAT calculation Celery task.
Runs 1st of each month, calculates output/input VAT for all active companies.
Enhanced: also generates PDV-S reports and sends WhatsApp summary to Marija.
"""
import logging
import datetime
from celery import shared_task
from decimal import Decimal

logger = logging.getLogger(__name__)

# Marija's phone for PDV notifications
MARIJA_PHONE = '385976091655'


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def monthly_vat_calculation(self):
    """
    Monthly VAT (PDV) calculation for all active companies.
    Runs on the 1st of each month, calculates for the PREVIOUS month.
    Creates TaxPeriod, PDVSReport, and sends WhatsApp summary.
    """
    from companies.models import Company
    from konto.services_file import calculate_vat_period

    today = datetime.date.today()
    # Calculate for previous month
    if today.month == 1:
        target_year = today.year - 1
        target_month = 12
    else:
        target_year = today.year
        target_month = today.month - 1

    companies = Company.objects.filter(is_active=True)
    results = []
    total_obveza = Decimal('0')
    obveznik_count = 0

    for company in companies:
        try:
            # Calculate VAT period
            period = calculate_vat_period(
                company=company,
                period_type="monthly",
                year=target_year,
                month=target_month,
            )
            logger.info(
                "VAT calculated for %s %02d/%d: output=%.2f input=%.2f payable=%.2f",
                company.name, target_month, target_year,
                period.total_output_vat, period.total_input_vat, period.vat_payable,
            )

            # Create PDV-S report if HR company and obveznik
            pdvs_report = None
            country = getattr(company, "country", "HR")
            pdv_status = getattr(company, "pdv_status", "none")
            if country == "HR" and pdv_status == "obveznik":
                pdvs_report = _create_pdvs_report(company, period, target_year, target_month)
                obveznik_count += 1
                total_obveza += period.vat_payable

            results.append({
                "company": company.name,
                "period": f"{target_month:02d}/{target_year}",
                "output_vat": float(period.total_output_vat),
                "input_vat": float(period.total_input_vat),
                "vat_payable": float(period.vat_payable),
                "pdvs_created": pdvs_report is not None,
            })

        except (ValueError, TypeError) as exc:
            logger.error(
                "VAT calculation failed for %s: %s", company.name, exc,
                exc_info=True,
            )
            results.append({
                "company": company.name,
                "error": str(exc),
            })

    # Send WhatsApp summary to Marija
    _send_pdv_whatsapp_summary(target_year, target_month, results, obveznik_count, total_obveza)

    logger.info("Monthly VAT calculation complete: %d companies processed", len(results))
    return results


def _create_pdvs_report(company, tax_period, year, month):
    """Create or update PDV-S report from TaxPeriod data."""
    try:
        from pdv_s.service import generate_pdv_s_from_tax_period
        return generate_pdv_s_from_tax_period(company, year, month)
    except ImportError as exc:
        logger.error("PDV-S report creation failed for %s: %s", company.name, exc)
        return None


def _send_pdv_whatsapp_summary(year, month, results, obveznik_count, total_obveza):
    """Send WhatsApp summary of monthly PDV calculation to Marija."""
    try:
        from core.whatsapp_tasks import send_whatsapp_text_task

        ok_count = sum(1 for r in results if 'error' not in r)
        err_count = sum(1 for r in results if 'error' in r)

        # Top 5 by VAT payable
        top5 = sorted(
            [r for r in results if 'error' not in r and r.get('vat_payable', 0) != 0],
            key=lambda x: abs(x['vat_payable']),
            reverse=True,
        )[:5]

        top5_lines = []
        for r in top5:
            vp = r['vat_payable']
            arrow = '+' if vp > 0 else ''
            top5_lines.append(f"  {r['company']}: {arrow}{vp:,.2f} EUR")

        msg = (
            f"LIMIT CONNECT — PDV obracun {month:02d}/{year}\n"
            f"{'=' * 35}\n"
            f"Firme obradene: {ok_count}\n"
            f"PDV-S kreirano: {obveznik_count}\n"
            f"Ukupna obveza: {float(total_obveza):,.2f} EUR\n"
        )

        if err_count:
            msg += f"Greske: {err_count}\n"

        if top5_lines:
            msg += "\nTop 5 po PDV obvezi:\n" + "\n".join(top5_lines) + "\n"

        msg += (
            f"\nXML-ovi spremni za preuzimanje:\n"
            f"https://limit-connect.com/pdv-s/batch-xml/{year}/{month}/\n"
            f"\nDashboard:\n"
            f"https://limit-connect.com/konto/reports/tax-dashboard/"
        )

        send_whatsapp_text_task.delay(MARIJA_PHONE, msg)
        logger.info("WhatsApp PDV summary sent to Marija")

    except (ValueError, TypeError) as exc:
        logger.error("WhatsApp PDV summary failed: %s", exc)
