import secrets
import string

from django.db import models


def _gen_seal_token():
    """8-char alphanumeric token, URL-safe, uppercase."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class ValidationLog(models.Model):
    TYPES = [("oib_hr", "OIB HR"), ("vat_eu", "VAT EU"), ("iban", "IBAN"), ("mbs", "MBS"), ("cross", "Cross")]
    validation_type = models.CharField(max_length=20, choices=TYPES)
    input_hash = models.CharField(max_length=64)
    is_valid = models.BooleanField()
    is_api_call = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    response_ms = models.IntegerField(default=0)

    class Meta:
        db_table = "evalidator_log"
        indexes = [models.Index(fields=["validation_type", "created_at"])]


class APIKey(models.Model):
    PLANS = [("free", "Free 100/day"), ("starter", "1k/day"), ("pro", "10k/day"), ("enterprise", "Unlimited")]
    name = models.CharField(max_length=200)
    email = models.EmailField()
    key_hash = models.CharField(max_length=64, unique=True)
    plan = models.CharField(max_length=20, choices=PLANS, default="free")
    daily_limit = models.IntegerField(default=100)
    daily_used = models.IntegerField(default=0)
    last_reset = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evalidator_apikey"

    def can_use(self):
        from django.utils import timezone

        today = timezone.now().date()
        if self.last_reset < today:
            self.daily_used = 0
            self.last_reset = today
            self.save(update_fields=["daily_used", "last_reset"])
        return self.is_active and self.daily_used < self.daily_limit


class DocumentSeal(models.Model):
    """
    Digitalni pečat vjerodostojnosti dokumenta.

    Generira se pri slanju ili eksplicitnom pečaćenju dokumenta.
    Token je 8-char URL-safe kod koji se ugrađuje u QR i PDF footer.

    Zakonski okvir:
    - eIDAS Art. 41: electronic timestamp = pravna presumpcija integriteta
    - GoBD §14b: neopoziv, vremenski označen, dostupan na zahtjev
    - Croatian ZED (NN 150/05): digitalni dokument s timestampom = original

    Verifikacija: https://evalidator.eu/verify/<seal_token>/
    """

    # Identifikacija dokumenta
    seal_token = models.CharField(
        max_length=8,
        unique=True,
        default=_gen_seal_token,
        db_index=True,
        help_text="8-char kod (URL-safe). Embed u QR i PDF footer.",
    )
    sha256_hash = models.CharField(
        max_length=64, db_index=True, help_text="SHA-256 hex digest sadržaja datoteke pri pečaćenju."
    )

    # Veza na arhivski entry (optional — može biti i standalone)
    arhiva_entry_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    arhiva_company_id = models.PositiveIntegerField(null=True, blank=True)

    # Metapodaci dokumenta (denormalizirani za prikaz na verify stranici)
    doc_number = models.CharField(max_length=255, blank=True)
    doc_date = models.DateField(null=True, blank=True)
    partner_name = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="EUR")
    issuer_name = models.CharField(max_length=200, blank=True, help_text="Naziv firme koja je pečatila")
    issuer_country = models.CharField(max_length=2, blank=True, default="HR")

    # Timestamp i validnost
    sealed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sealed_by_user_id = models.PositiveIntegerField(null=True, blank=True)
    sealed_by_username = models.CharField(max_length=150, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Null = trajno. Inače: datum isteka (npr. 10 godina GoBD)."
    )

    # Slanje
    send_channel = models.CharField(max_length=50, blank=True, help_text="email, whatsapp, portal, datev")
    viral_code = models.CharField(
        max_length=12, blank=True, db_index=True, help_text="Viralni kod za onboarding landing page"
    )

    # Audit
    verify_count = models.PositiveIntegerField(default=0, help_text="Koliko puta je verifikacijska stranica otvorena")
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "evalidator_document_seal"
        ordering = ["-sealed_at"]
        indexes = [
            models.Index(fields=["sha256_hash"]),
            models.Index(fields=["viral_code"]),
            models.Index(fields=["arhiva_entry_id"]),
        ]

    def __str__(self):
        return f"Pečat {self.seal_token} — {self.doc_number or 'bez broja'} ({self.sealed_at.date()})"

    @property
    def is_valid(self):
        from django.utils import timezone

        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    @property
    def verify_url(self):
        return f"https://evalidator.eu/verify/{self.seal_token}/"
