"""
konto/tasks_vat.py
Monthly VAT calculation Celery task.
Runs 1st of each month, calculates output/input VAT for all active companies.
"""
import logging
import datetime
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def monthly_vat_calculation(self):
    """
    Monthly VAT (PDV) calculation for all active companies.
    Runs on the 1st of each month, calculates for the PREVIOUS month.
    Creates TaxPeriod and optionally PDVSReport.
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

            # Create PDV-S report if pdv_s module exists and company is HR
            pdvs_report = None
            country = getattr(company, "country", "HR")
            if country == "HR":
                pdvs_report = _create_pdvs_report(company, period, target_year, target_month)

            results.append({
                "company": company.name,
                "period": f"{target_month:02d}/{target_year}",
                "output_vat": float(period.total_output_vat),
                "input_vat": float(period.total_input_vat),
                "vat_payable": float(period.vat_payable),
                "pdvs_created": pdvs_report is not None,
            })

        except Exception as exc:
            logger.error(
                "VAT calculation failed for %s: %s", company.name, exc,
                exc_info=True,
            )
            results.append({
                "company": company.name,
                "error": str(exc),
            })

    logger.info("Monthly VAT calculation complete: %d companies processed", len(results))
    return results


def _create_pdvs_report(company, tax_period, year, month):
    """Create or update PDV-S report from TaxPeriod data."""
    try:
        from pdv_s.models import PDVSReport
    except ImportError:
        return None

    from decimal import Decimal
    from konto.models import TaxLineDetail

    report, _ = PDVSReport.objects.update_or_create(
        company=company, year=year, month=month,
        defaults={"status": "draft"},
    )

    # Map tax rates to PDV-S fields
    line_details = TaxLineDetail.objects.filter(period=tax_period)

    # Reset output fields
    report.ii1_base = Decimal("0")
    report.ii1_tax = Decimal("0")
    report.ii2_base = Decimal("0")
    report.ii2_tax = Decimal("0")
    report.ii3_base = Decimal("0")
    report.ii3_tax = Decimal("0")

    for ld in line_details:
        rate = ld.tax_rate
        if rate == Decimal("25"):
            report.ii1_base = ld.revenue_base
            report.ii1_tax = ld.output_vat
        elif rate == Decimal("13"):
            report.ii2_base = ld.revenue_base
            report.ii2_tax = ld.output_vat
        elif rate == Decimal("5"):
            report.ii3_base = ld.revenue_base
            report.ii3_tax = ld.output_vat

    # Input VAT (pretporez) from TaxPeriod
    report.i1_base = Decimal("0")
    report.i1_tax = tax_period.total_input_vat
    report.iii_total_pretporez = tax_period.total_input_vat

    # Totals
    report.iv_pdv_isporuke = tax_period.total_output_vat
    report.iv_pretporez = tax_period.total_input_vat
    report.iv_razlika = tax_period.total_output_vat - tax_period.total_input_vat

    report.save()
    logger.info("PDV-S report created/updated for %s %02d/%d", company.name, month, year)
    return report
