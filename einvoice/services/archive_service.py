"""S3/MinIO Archive Service with SHA-256 integrity verification."""

import logging

from django.conf import settings

from einvoice.models import DocumentArchive

logger = logging.getLogger("propter.einvoice.archive")


def _get_s3_client():
    """Lazy S3 client — boto3 imported only when actually used."""
    try:
        import boto3
    except ImportError:
        logger.error("boto3 not installed — S3 archive disabled")
        return None
    return boto3.client(
        "s3",
        endpoint_url=getattr(settings, "S3_ENDPOINT_URL", "http://minio:9000"),
        aws_access_key_id=getattr(settings, "S3_ACCESS_KEY", ""),
        aws_secret_access_key=getattr(settings, "S3_SECRET_KEY", ""),
        region_name=getattr(settings, "S3_REGION", "eu-central-1"),
    )


class ArchiveService:
    def __init__(self):
        self._s3 = None
        self.bucket = getattr(settings, "S3_ARCHIVE_BUCKET", "propter-einvoice-archive")

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = _get_s3_client()
        return self._s3

    def archive_message(self, message):
        content = message.ubl_xml.encode("utf-8") if isinstance(message.ubl_xml, str) else message.ubl_xml
        sha256 = DocumentArchive.compute_hash(content)

        existing = DocumentArchive.objects.filter(sha256_hash=sha256).first()
        if existing:
            logger.info(f"Document already archived: {sha256[:16]}...")
            return existing

        s3_key = DocumentArchive.generate_s3_key(str(message.company_id), str(message.id))

        if self.s3:
            try:
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType="application/xml",
                    Metadata={"sha256": sha256, "invoice-number": message.invoice_number or ""},
                )
            except Exception as e:
                logger.critical(f"S3 upload failed (document NOT protected by Object Lock!): {e}")
                raise
        else:
            logger.warning(f"S3 not available — archiving metadata only for {message.invoice_number}")

        if message.direction == "OUT":
            doc_type = (
                DocumentArchive.DocumentType.OUTBOUND_CREDIT
                if message.document_type == "CREDIT_NOTE"
                else DocumentArchive.DocumentType.OUTBOUND_INVOICE
            )
        else:
            doc_type = (
                DocumentArchive.DocumentType.INBOUND_CREDIT
                if message.document_type == "CREDIT_NOTE"
                else DocumentArchive.DocumentType.INBOUND_INVOICE
            )

        archive = DocumentArchive.objects.create(
            company=message.company,
            as4_message=message,
            document_type=doc_type,
            s3_key=s3_key,
            file_size_bytes=len(content),
            sha256_hash=sha256,
            invoice_number=message.invoice_number,
            invoice_date=message.created_at.date() if message.created_at else None,
            sender_name=message.sender_name,
            receiver_name=message.receiver_name,
            amount=message.invoice_amount,
            currency=message.invoice_currency,
            retention_until=DocumentArchive.calculate_retention_date(
                message.created_at.date() if message.created_at else None
            ),
        )

        message.archive_s3_key = s3_key
        message.archive_sha256 = sha256
        message.transition_to("ARCHIVED", detail=f"Arhivirano: {sha256[:16]}...")
        logger.info(f"Document archived: {message.invoice_number} -> {s3_key}")
        return archive

    def verify_document(self, sha256_hash):
        archive = DocumentArchive.objects.filter(sha256_hash=sha256_hash).first()
        if not archive:
            return {
                "verified": False,
                "integrity_check": "NOT_FOUND",
                "message": "Dokument s ovim hash-om nije pronaden u arhivi.",
            }

        if not self.s3:
            return {
                "verified": True,
                "integrity_check": "S3_UNAVAILABLE",
                "message": "S3 nije dostupan za verifikaciju.",
            }

        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=archive.s3_key)
            content = response["Body"].read()
            computed_hash = DocumentArchive.compute_hash(content)
            integrity_ok = computed_hash == sha256_hash
            return {
                "verified": True,
                "integrity_check": "PASS" if integrity_ok else "FAIL",
                "hash_match": integrity_ok,
                "document_metadata": {
                    "invoice_number": archive.invoice_number,
                    "invoice_date": str(archive.invoice_date),
                    "sender": archive.sender_name,
                    "receiver": archive.receiver_name,
                    "amount": str(archive.amount),
                    "currency": archive.currency,
                    "archived_at": archive.archived_at.isoformat(),
                    "retention_until": str(archive.retention_until),
                    "document_type": archive.get_document_type_display(),
                },
                "message": "Dokument verificiran." if integrity_ok else "UPOZORENJE: Dokument modificiran!",
            }
        except IOError as e:
            return {"verified": False, "integrity_check": "ERROR", "message": f"Greska: {e}"}

    def download_archived_document(self, archive_id, company_id):
        archive = DocumentArchive.objects.filter(id=archive_id, company_id=company_id).first()
        if not archive or not self.s3:
            return None
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=archive.s3_key)
            return response["Body"].read()
        except IOError:
            return None
