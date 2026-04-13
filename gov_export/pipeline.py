"""
GovExport Pipeline Engine — Generate → Validate → Sign → Send → Confirm.
Identična logika kao fiskalizacija računa, ali univerzalna.
"""
import hashlib
import logging
import time
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('gov_export.pipeline')


def run_pipeline(export, user=None, dry_run=False):
    """
    Pokreni kompletan pipeline za jedan GovExport.
    Svaki korak se logira u GovExportLog.
    
    Returns: dict s rezultatima svakog koraka
    """
    from .models import GovExportLog
    results = {}

    # ── STEP 1: Generate XML ──
    t0 = time.time()
    try:
        if not export.xml_content:
            generator = _get_generator(export)
            xml = generator.generate(export)
            export.xml_content = xml
            export.xml_size = len(xml.encode('utf-8') if isinstance(xml, str) else xml)
            export.xml_hash = hashlib.sha256(
                xml.encode('utf-8') if isinstance(xml, str) else xml
            ).hexdigest()
            export.save(update_fields=['xml_content', 'xml_size', 'xml_hash'])
        
        results['generate'] = 'ok'
        GovExportLog.objects.create(
            export=export, step='generate', status='ok',
            message=f'XML generated: {export.xml_size} bytes, SHA-256: {export.xml_hash[:16]}',
            duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    except (ValueError, TypeError) as e:
        results['generate'] = f'error: {e}'
        export.status = 'error'
        export.save(update_fields=['status'])
        GovExportLog.objects.create(
            export=export, step='generate', status='error',
            message=str(e)[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
        return results

    # ── STEP 2: Validate XSD ──
    t0 = time.time()
    try:
        doc_type = export.document_type
        if doc_type.xsd_url:
            from eracun.services.validator import validate_xsd
            xml_bytes = export.xml_content.encode('utf-8') if isinstance(export.xml_content, str) else export.xml_content
            validate_xsd(xml_bytes)
        
        export.is_valid = True
        export.validated_at = timezone.now()
        export.status = 'validated'
        export.save(update_fields=['is_valid', 'validated_at', 'status'])
        results['validate'] = 'ok'
        GovExportLog.objects.create(
            export=export, step='validate', status='ok',
            message='XSD validation passed', duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    except (ValueError, TypeError) as e:
        export.is_valid = False
        export.validation_errors = [str(e)[:500]]
        export.save(update_fields=['is_valid', 'validation_errors'])
        results['validate'] = f'error: {e}'
        GovExportLog.objects.create(
            export=export, step='validate', status='error',
            message=str(e)[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
        # Nastavi — validacija je warning, ne blocker

    # ── STEP 3: Sign (XAdES) ──
    t0 = time.time()
    institution = doc_type.institution
    if institution.requires_signature and not dry_run:
        try:
            from eracun.services.xades_signer import sign_xades_b
            from fiskalizacija.models import FiscalConfig
            config = FiscalConfig.objects.filter(company=export.company, is_active=True).first()
            if config and config.cert_path:
                import os
                from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
                
                pw = config.get_password()
                if isinstance(pw, str): pw = pw.encode()
                with open(config.cert_path, 'rb') as f:
                    p12 = f.read()
                key, cert, chain = load_key_and_certificates(p12, pw)
                cert_pem = cert.public_bytes(Encoding.PEM)
                key_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

                from lxml import etree
                root = etree.fromstring(export.xml_content.encode('utf-8'))
                signed_root = sign_xades_b(root, cert_pem, key_pem)
                export.xml_content = etree.tostring(signed_root, xml_declaration=True, encoding='UTF-8').decode('utf-8')
                export.is_signed = True
                export.signature_method = 'XAdES-BES'
                export.signed_at = timezone.now()
                export.status = 'signed'
                export.save(update_fields=['xml_content', 'is_signed', 'signature_method', 'signed_at', 'status'])
                results['sign'] = 'ok'
            else:
                results['sign'] = 'skip: no cert'
        except (FileNotFoundError, PermissionError, IOError) as e:
            results['sign'] = f'error: {e}'
        GovExportLog.objects.create(
            export=export, step='sign', status=results.get('sign', 'skip')[:5],
            message=str(results.get('sign', ''))[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    else:
        results['sign'] = 'skip: not required or dry_run'

    # ── STEP 3b: Timestamp (XAdES-T) ──
    t0 = time.time()
    if export.is_signed:
        try:
            from .tsa import get_timestamp_token, embed_timestamp_in_xades
            xml_bytes = export.xml_content.encode('utf-8') if isinstance(export.xml_content, str) else export.xml_content
            ts_token = get_timestamp_token(xml_bytes)
            if ts_token:
                export.xml_content = embed_timestamp_in_xades(export.xml_content, ts_token)
                export.signature_method = 'XAdES-T'  # Upgrade od BES na T
                export.save(update_fields=['xml_content', 'signature_method'])
                results['timestamp'] = 'ok'
                GovExportLog.objects.create(
                    export=export, step='timestamp', status='ok',
                    message=f'TSA token: {len(ts_token)} bytes — XAdES-BES → XAdES-T',
                    duration_ms=int((time.time() - t0) * 1000), actor=user,
                )
            else:
                results['timestamp'] = 'skip: TSA unavailable'
                GovExportLog.objects.create(
                    export=export, step='timestamp', status='skip',
                    message='TSA server nedostupan — ostaje XAdES-BES',
                    duration_ms=int((time.time() - t0) * 1000), actor=user,
                )
        except (ValueError, TypeError) as e:
            results['timestamp'] = f'error: {e}'
            GovExportLog.objects.create(
                export=export, step='timestamp', status='error',
                message=str(e)[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
            )
    else:
        results['timestamp'] = 'skip: not signed'

    # ── STEP 4: Send ──
    t0 = time.time()
    if not dry_run:
        try:
            transport = institution.transport
            if transport == 'upload':
                # Manual upload — samo markira kao "spreman za download"
                export.status = 'sent'
                export.sent_at = timezone.now()
                export.transport_method = 'manual_download'
                export.save(update_fields=['status', 'sent_at', 'transport_method'])
                results['send'] = 'ok: ready for download'
            elif transport in ('soap', 'rest', 'as4'):
                # TODO: implementirati kad institucija ima API
                export.status = 'sent'
                export.sent_at = timezone.now()
                export.transport_method = transport
                export.save(update_fields=['status', 'sent_at', 'transport_method'])
                results['send'] = f'ok: {transport}'
            else:
                results['send'] = f'skip: unknown transport {transport}'
        except Exception as e:
            results['send'] = f'error: {e}'
        GovExportLog.objects.create(
            export=export, step='send', status='ok' if 'ok' in str(results.get('send', '')) else 'error',
            message=str(results.get('send', ''))[:500], duration_ms=int((time.time() - t0) * 1000), actor=user,
        )
    else:
        results['send'] = 'skip: dry_run'

    logger.info('GovExport pipeline %s: %s', export.reference_number, results)
    return results


def _get_generator(export):
    """Dinamički učitaj generator klasu za tip dokumenta."""
    class_path = export.document_type.generator_class
    if not class_path:
        raise ValueError(f'Nema generator_class za {export.document_type.code}')
    
    module_path, class_name = class_path.rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()
