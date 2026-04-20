"""
core/qr_registry_models.py — Globalni QR Registry

Svaki objekt koji ulazi ili izlazi iz sustava dobija jedan QRToken.
Token je 16-hex alfanumerički string, stabilan kroz cijeli životni ciklus objekta.

Arhitektura:
  - object_type: "arhiva.entry" | "invoicing.invoice" | "pos.receipt" | ...
  - object_ref:  UUID/PK objekta (CharField)
  - token:       8-hex (shortlink) + 32-hex (full) — dva oblika
  - verify_url:  /qr/<token>/ (javno, bez logina)

Tri stvari iz budućnosti:
  1. Verifiable Credential (vc_payload JSON) — W3C VC embedded u QR
  2. Honeypot/Tamper (scan_count, geo_log JSON, tamper_flag)
  3. Viral (viral_code, viral_clicks, viral_conversions)
"""

import secrets
import uuid

from django.db import models
from django.utils import timezone


def _gen_token() -> str:
    """32-char hex token — globalno jedinstven."""
    return secrets.token_hex(16)


def _gen_short() -> str:
    """8-char alphanumerički shortlink."""
    return secrets.token_urlsafe(6)[:8]


class QRToken(models.Model):
    """
    Centralni registar svih QR kodova u sustavu.
    Jedan objekt = jedan QRToken (idempotentno).
    """

    OBJECT_TYPES = [
        ("arhiva.entry", "Arhiva dokument"),
        ("invoicing.invoice", "Račun"),
        ("pos.receipt", "POS isječak"),
        ("evalidator.block", "eArhivator blok"),
        ("documents.document", "Dokument"),
        ("partners.company", "Partner/firma"),
        ("no_limit.member", "NO LIMIT član"),
        ("memio.lektira", "Lektira potvrda"),
        ("generic", "Ostalo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Što se pečati
    object_type = models.CharField(max_length=60, choices=OBJECT_TYPES, db_index=True)
    object_ref = models.CharField(max_length=200, db_index=True)  # UUID/PK objekta

    # Tokeni
    token = models.CharField(
        max_length=32, unique=True, default=_gen_token, help_text="Puni 32-hex token — stabilan URL"
    )
    short = models.CharField(max_length=10, unique=True, default=_gen_short, help_text="8-char shortlink za printanje")

    # Metapodaci (denormalizirani za brzi verify bez JOIN-a)
    label = models.CharField(max_length=200, blank=True, help_text="Kratak opis: 'Račun HR-2026-0042'")
    company_name = models.CharField(max_length=200, blank=True)
    created_by = models.CharField(max_length=100, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Null = ne istječe (trajni dokument)")
    is_active = models.BooleanField(default=True, db_index=True)

    # ── Budućnost 1: W3C Verifiable Credential ──────────────────────────────
    vc_payload = models.JSONField(
        default=dict, blank=True, help_text="W3C VC 1.1 payload — offline verifikacija bez servera"
    )

    # ── Budućnost 2: Honeypot & Tamper Detection ─────────────────────────────
    scan_count = models.PositiveIntegerField(default=0)
    last_scan = models.DateTimeField(null=True, blank=True)
    geo_log = models.JSONField(default=list, blank=True, help_text="Lista zadnjih 10 skenova: [{ip, country, ts, ua}]")
    tamper_flag = models.BooleanField(default=False, help_text="Automatski: True ako > 5 geo-lokacija u 24h")
    tamper_alert_sent = models.BooleanField(default=False)

    # ── Budućnost 3: Viral Krug ───────────────────────────────────────────────
    viral_code = models.CharField(
        max_length=12, blank=True, db_index=True, help_text="Referral kod za viralni tracking"
    )
    viral_clicks = models.PositiveIntegerField(default=0)
    viral_conversions = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "core"
        verbose_name = "QR Token"
        verbose_name_plural = "QR Tokeni"
        indexes = [
            models.Index(fields=["object_type", "object_ref"]),
            models.Index(fields=["token"]),
            models.Index(fields=["short"]),
            models.Index(fields=["tamper_flag", "created_at"]),
        ]
        constraints = [models.UniqueConstraint(fields=["object_type", "object_ref"], name="qr_registry_unique_object")]

    def __str__(self):
        return f"QR:{self.short} — {self.object_type}:{self.object_ref[:20]}"

    @property
    def verify_url(self) -> str:
        return f"/qr/{self.token}/"

    @property
    def short_url(self) -> str:
        return f"/qr/s/{self.short}/"

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    def record_scan(self, ip: str = "", country: str = "", ua: str = "") -> None:
        """Bilježi sken, ažurira honeypot log, provjerava tamper."""
        from django.utils import timezone as tz

        self.scan_count += 1
        self.last_scan = tz.now()

        entry = {
            "ip": ip[:45],
            "country": country[:5],
            "ua": ua[:100],
            "ts": tz.now().isoformat(),
        }
        log = self.geo_log or []
        log.append(entry)
        self.geo_log = log[-10:]  # čuvaj zadnjih 10

        # Tamper check: > 5 različitih IP-a u zadnjih 24h
        cutoff = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_ips = {e["ip"] for e in self.geo_log if e.get("ts", "") >= cutoff.isoformat()}
        if len(recent_ips) >= 5 and not self.tamper_flag:
            self.tamper_flag = True
            self._send_tamper_alert()

        self.save(update_fields=["scan_count", "last_scan", "geo_log", "tamper_flag", "tamper_alert_sent"])

        # Viral: inkrement klika
        if self.viral_code:
            type(self).objects.filter(pk=self.pk).update(viral_clicks=models.F("viral_clicks") + 1)

    def _send_tamper_alert(self) -> None:
        """WhatsApp + email alert vlasniku — async task."""
        if self.tamper_alert_sent:
            return
        self.tamper_alert_sent = True
        try:
            from core.qr_registry import send_tamper_alert_async

            send_tamper_alert_async(str(self.id))
        except Exception:
            pass


class QRScanLog(models.Model):
    """
    Detaljni log svakog skeniranja (za analytics).
    Čuva se 90 dana, zatim Celery Beat briše.
    """

    qr_token = models.ForeignKey(QRToken, on_delete=models.CASCADE, related_name="scan_logs")
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=5, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    referrer = models.URLField(blank=True)
    converted = models.BooleanField(default=False, help_text="True ako je doveo do registracije")

    class Meta:
        app_label = "core"
        verbose_name = "QR Sken Log"
        verbose_name_plural = "QR Sken Logovi"
        ordering = ["-scanned_at"]
        indexes = [
            models.Index(fields=["qr_token", "scanned_at"]),
        ]

    def __str__(self):
        return f"Sken {self.qr_token.short} @ {self.scanned_at:%Y-%m-%d %H:%M}"
