"""
Signal: PayrollRun status → 'PAID' → generate payslip PDFs + email to workers.

Flow:
  1. PayrollRun status changes to PAID
  2. For each Payslip → generate PDF via WeasyPrint
  3. Email PDF to worker (if worker has email)
"""
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger('payroll.signals')


@receiver(pre_save, sender='payroll.PayrollRun')
def payroll_paid_send_payslips(sender, instance, **kwargs):
    """When PayrollRun changes to PAID, queue payslip PDF generation + email."""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status or instance.status != 'PAID':
        return

    # Use post_save would be cleaner but pre_save lets us catch the transition
    # We'll process after the save completes using transaction.on_commit
    from django.db import transaction
    transaction.on_commit(lambda: _process_payslips(instance.pk))


def _process_payslips(payroll_run_id):
    """Generate PDF payslips and email to workers."""
    from payroll.models import PayrollRun
    try:
        run = PayrollRun.objects.select_related('company').get(pk=payroll_run_id)
    except PayrollRun.DoesNotExist:
        return

    payslips = run.payslips.select_related('user').all()
    for payslip in payslips:
        try:
            _send_payslip_email(payslip, run)
        except Exception:
            logger.exception('Failed to send payslip for user %s', payslip.user_id)


def _send_payslip_email(payslip, run):
    """Generate PDF and send via email."""
    import weasyprint
    from django.template.loader import render_to_string
    from django.core.mail import EmailMessage

    user = payslip.user
    if not user.email:
        logger.info('No email for user %s, skipping payslip', user.username)
        return

    html = render_to_string('payroll/payslip_pdf.html', {
        'payslip': payslip,
        'run': run,
        'company': run.company,
        'user': user,
        'generated_at': timezone.now(),
    })

    pdf = weasyprint.HTML(string=html).write_pdf()

    subject = 'Obracunski listic — {}/{:02d} — {}'.format(
        run.year, run.month, run.company.name
    )
    body = (
        'Postovani {},\n\n'
        'U prilogu je Vas obracunski listic za {}/{:02d}.\n\n'
        'Neto za isplatu: {:.2f} EUR\n\n'
        'Srdacno,\n{}'
    ).format(
        user.get_full_name() or user.username,
        run.year, run.month,
        payslip.net_amount,
        run.company.name,
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        to=[user.email],
    )
    email.attach(
        'Payslip-{}-{:02d}-{}.pdf'.format(run.year, run.month, user.username),
        pdf,
        'application/pdf',
    )
    email.send(fail_silently=False)
    logger.info('Payslip sent to %s for %s/%02d', user.email, run.year, run.month)
