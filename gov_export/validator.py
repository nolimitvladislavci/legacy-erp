"""
CroXML Verify — javna stranica za provjeru potpisa GovExport XML-ova.
Inspektor uploada XML → sustav provjerava kriptografski potpis → zelena/crvena.
BEZ AUTENTIFIKACIJE — javno dostupno.
"""
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import hashlib
from django.db import DatabaseError


@csrf_exempt
def public_validator(request):
    """GET: forma za upload. POST: provjera XML-a."""
    result = None

    if request.method == 'POST' and request.FILES.get('xml_file'):
        xml_file = request.FILES['xml_file']
        xml_bytes = xml_file.read()
        xml_str = xml_bytes.decode('utf-8', errors='replace')

        result = {
            'filename': xml_file.name,
            'size': len(xml_bytes),
            'sha256': hashlib.sha256(xml_bytes).hexdigest(),
            'valid_xml': False,
            'has_signature': False,
            'signature_valid': False,
            'issuer': '',
            'generated': '',
            'doc_type': '',
        }

        # Parse XML
        try:
            from lxml import etree
            root = etree.fromstring(xml_bytes)
            result['valid_xml'] = True
            result['doc_type'] = root.tag.split('}')[-1] if '}' in root.tag else root.tag

            # Extract metadata
            issuer_el = root.find('.//{*}Issuer/{*}Name')
            if issuer_el is not None:
                result['issuer'] = issuer_el.text or ''
            oib_el = root.find('.//{*}Issuer/{*}OIB')
            if oib_el is not None:
                result['issuer'] += f' (OIB: {oib_el.text})'

            generated = root.get('generated', '')
            result['generated'] = generated

            # Provjeri XAdES potpis
            sig_el = root.find('.//{http://www.w3.org/2000/09/xmldsig#}Signature')
            if sig_el is not None:
                result['has_signature'] = True
                # Provjeri potpis
                try:
                    from signxml import XMLVerifier
                    XMLVerifier().verify(root)
                    result['signature_valid'] = True
                except ImportError as e:
                    result['signature_error'] = str(e)[:200]

            # Provjeri u bazi postoji li ovaj export
            try:
                from gov_export.models import GovExport
                export = GovExport.objects.filter(xml_hash=result['sha256']).first()
                if export:
                    result['registered'] = True
                    result['reference'] = export.reference_number
                    result['status'] = export.get_status_display()
                else:
                    result['registered'] = False
            except DatabaseError:
                result['registered'] = False

        except DatabaseError as e:
            result['parse_error'] = str(e)[:200]

    return render(request, 'gov_export/validator.html', {'result': result})
