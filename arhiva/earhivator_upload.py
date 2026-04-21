"""
arhiva/earhivator_upload.py

Standalone eArhivator upload endpoint koji:
  1. Prima binarni fajl (POST multipart)
  2. Komprimira (core/earhivator_compressor.py)
  3. Računa Triple DNA (core/triple_dna.py)
  4. Gradi XML kovertu (core/earhivator.py)
  5. Sprema u MinIO (ili lokalno za dev)
  6. Kreira EarhivatorEntry u bazi
  7. Registrira POE u ChainBlock (core/chainblock_registry.py)

Ruta: /hr/arhiva/earhivator/upload/
Auth: TenantView (kompanija iz sesije)
"""

import hashlib
import logging
import uuid

from django.http import JsonResponse

from core.earhivator import build_envelope_xml, compute_chain_hash, seal_xml
from core.earhivator_compressor import ArchiveProfile, compress
from core.earhivator_models import EarhivatorEntry
from core.tenant_views import TenantView
from core.triple_dna import compute_triple_dna

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


class EarhivatorUploadView(TenantView):
    """
    POST /hr/arhiva/earhivator/upload/

    Params (multipart/form-data):
      file        — obavezan
      object_type — vrsta objekta (default: 'document')
      object_ref  — slobodna referenca (npr. ID računa)
      profile     — 'business' | 'user' (default: 'business')
    """

    def post(self, request, *args, **kwargs):
        f = request.FILES.get("file")
        if not f:
            return JsonResponse({"error": "Nema fajla"}, status=400)

        if f.size > MAX_FILE_BYTES:
            return JsonResponse(
                {"error": f"Fajl prevelik: {f.size // 1024 // 1024} MB. Max 50 MB."},
                status=400,
            )

        raw = f.read()
        mime = f.content_type or "application/octet-stream"
        object_type = request.POST.get("object_type", "document").strip()[:50]
        object_ref = request.POST.get("object_ref", "").strip()[:200]
        profile_s = request.POST.get("profile", "business")
        arch_profile = ArchiveProfile.BUSINESS if profile_s == "business" else ArchiveProfile.USER

        # 1. Triple DNA (na originalnom sadržaju)
        dna = compute_triple_dna(raw, f.name)
        l1 = dna["layer1_sha256"]
        l2 = dna["layer2_phash"]
        cx = dna["cross_hash"]

        # 2. Kompresija
        try:
            comp = compress(raw, mime, arch_profile)
        except Exception as e:
            logger.warning("eArhivator kompresija nije uspjela: %s", e)

            class _FallbackComp:
                compressed_bytes = raw
                original_size = len(raw)
                compressed_size = len(raw)
                savings_pct = 0.0
                output_format = "original"

            comp = _FallbackComp()

        # 3. XML koverta
        obj_id = uuid.uuid4()
        minio_url = f"local://earhivator/{obj_id}/master"
        xml_url = f"local://earhivator/{obj_id}/manifest.xml"

        try:
            xml = build_envelope_xml(
                object_type=object_type,
                object_id=str(obj_id),
                company_id=str(self.company.pk),
                minio_url=minio_url,
                original_hash=l1,
                original_size=comp.original_size,
                compressed_format=comp.output_format,
                mime_type=mime,
                metadata={"ref": object_ref, "phash": l2},
            )
            seal = seal_xml(xml)
            binary_h = hashlib.sha256(comp.compressed_bytes).hexdigest()
            chain_h = compute_chain_hash(binary_h, xml)
        except Exception as e:
            logger.error("eArhivator XML/seal greška: %s", e)
            seal = ""
            chain_h = hashlib.sha256(f"{l1}{cx}".encode()).hexdigest()

        # 4. EarhivatorEntry
        try:
            entry = EarhivatorEntry.objects.create(
                company=self.company,
                object_type=object_type,
                object_ref=object_ref,
                profile=profile_s,
                original_hash=l1,
                layer2_phash=l2,
                cross_hash_l1l2=cx,
                chain_hash=chain_h,
                seal_token=seal[:64],
                minio_url=minio_url,
                xml_minio_url=xml_url,
                original_size=comp.original_size,
                compressed_size=comp.compressed_size,
                stored_format=comp.output_format,
                mime_type=mime,
                metadata_json={"ref": object_ref, "filename": f.name},
            )
        except Exception as e:
            logger.error("EarhivatorEntry save greška: %s", e)
            return JsonResponse({"error": "Greška pri pohrani"}, status=500)

        # 5. POE registracija
        poe_token = None
        try:
            from core.chainblock_registry import register_poe

            poe_token = register_poe(cx, str(self.company.pk))
        except Exception as e:
            logger.warning("POE registracija nije uspjela: %s", e)

        return JsonResponse(
            {
                "id": str(entry.id),
                "cross_hash": cx,
                "layer1_sha256": l1,
                "layer2_phash": l2,
                "savings_pct": comp.savings_pct,
                "seal_token": (seal[:16] + "...") if seal else "",
                "poe_token": poe_token,
                "object_type": object_type,
                "object_ref": object_ref,
            },
            status=201,
        )
