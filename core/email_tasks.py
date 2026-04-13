"""
Centralized Celery email tasks for LIMIT Connect ERP.
All email sending goes through these tasks for async processing.
"""
import base64
import logging

from celery import shared_task
from django.core.mail import EmailMessage, send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, retry_backoff=True, autoretry_for=(Exception,))
def send_email_task(self, subject, message, from_email, recipient_list, html_message=None, fail_silently=False):
    """Drop-in async replacement for django.core.mail.send_mail."""
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=fail_silently,
    )
    logger.info('Email sent: "%s" -> %s', subject, recipient_list)


@shared_task(bind=True, max_retries=3, retry_backoff=True, autoretry_for=(Exception,))
def send_email_with_attachment_task(self, subject, body, from_email, to_list,
                                     attachment_name, attachment_content_b64, content_type):
    """Send email with a single file attachment (base64-encoded content)."""
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=to_list,
    )
    attachment_content = base64.b64decode(attachment_content_b64)
    email.attach(attachment_name, attachment_content, content_type)
    email.send()
    logger.info('Email with attachment sent: "%s" -> %s', subject, to_list)


@shared_task(bind=True, max_retries=3, retry_backoff=True, autoretry_for=(Exception,))
def send_html_email_task(self, subject, text_body, html_body, from_email, recipient_list):
    """Send HTML email with plaintext fallback."""
    send_mail(
        subject=subject,
        message=text_body,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_body,
        fail_silently=False,
    )
    logger.info('HTML email sent: "%s" -> %s', subject, recipient_list)
