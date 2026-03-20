from django.db import models
from django.utils.translation import gettext_lazy as _


class Contact(models.Model):
    class ContactType(models.TextChoices):
        HAUSVERWALTUNG = "hausverwaltung", _("Hausverwaltung")
        MAKLER         = "makler",         _("Makler")
        ARCHITEKT      = "architekt",      _("Architekt")
        PRIVATPERSON   = "privatperson",   _("Privatperson")
        FIRMA          = "firma",          _("Firma")

    class Status(models.TextChoices):
        NEU          = "neu",          _("Neu")
        KONTAKTIERT  = "kontaktiert",  _("Kontaktiert")
        GEANTWORTET  = "geantwortet",  _("Geantwortet")
        INTERESSIERT = "interessiert", _("Interessiert")
        KLIENT       = "klient",       _("Klient")
        ABGELEHNT    = "abgelehnt",    _("Abgelehnt")

    class Source(models.TextChoices):
        MANUAL      = "manual",      _("Manuell")
        CSV         = "csv",         _("CSV Import")
        GOOGLE_MAPS = "google_maps", _("Google Maps")

    company      = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="outreach_contacts",
        verbose_name=_("Tvrtka"))
    name         = models.CharField(max_length=200, blank=True,  verbose_name=_("Name"))
    firm_name    = models.CharField(max_length=200, blank=True,  verbose_name=_("Firmenname"))
    email        = models.EmailField(verbose_name=_("E-Mail"))
    phone        = models.CharField(max_length=30, blank=True,   verbose_name=_("Telefon"))
    address      = models.CharField(max_length=255, blank=True,  verbose_name=_("Adresse"))
    city         = models.CharField(max_length=100, blank=True,  verbose_name=_("Stadt"))
    plz          = models.CharField(max_length=10, blank=True,   verbose_name=_("PLZ"))
    contact_type = models.CharField(max_length=20,
                                     choices=ContactType.choices,
                                     default=ContactType.FIRMA,
                                     verbose_name=_("Typ"))
    status       = models.CharField(max_length=20,
                                     choices=Status.choices,
                                     default=Status.NEU,
                                     verbose_name=_("Status"))
    source       = models.CharField(max_length=20,
                                     choices=Source.choices,
                                     default=Source.MANUAL,
                                     verbose_name=_("Quelle"))
    notes        = models.TextField(blank=True, verbose_name=_("Notizen"))
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Kontakt")
        verbose_name_plural = _("Kontakte")

    def __str__(self):
        return f"{self.firm_name or self.name} <{self.email}>"

    @property
    def display_name(self):
        return self.firm_name or self.name or self.email


class Campaign(models.Model):
    name             = models.CharField(max_length=200, verbose_name=_("Kampagnenname"))
    subject_template = models.CharField(max_length=300,
                                         verbose_name=_("Betreff-Vorlage"),
                                         help_text=_("Vars: {ime_firme}, {grad}, {tip_posla}"))
    body_template    = models.TextField(verbose_name=_("Inhalt-Vorlage"))
    send_per_day     = models.IntegerField(default=50, verbose_name=_("Senden pro Tag"))
    follow_up_days   = models.IntegerField(default=3,  verbose_name=_("Follow-up Tage"))
    active           = models.BooleanField(default=False, verbose_name=_("Aktiv"))
    stat_sent        = models.IntegerField(default=0)
    stat_opened      = models.IntegerField(default=0)
    stat_replied     = models.IntegerField(default=0)
    stat_interested  = models.IntegerField(default=0)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Kampagne")
        verbose_name_plural = _("Kampagnen")

    def __str__(self):
        return self.name

    def refresh_stats(self):
        cc = self.contacts.all()
        self.stat_sent    = cc.filter(status__in=["sent", "follow_up", "replied"]).count()
        self.stat_replied = cc.filter(status="replied").count()
        self.stat_interested = Contact.objects.filter(
            campaign_contacts__campaign=self, status="interessiert").count()
        self.save(update_fields=["stat_sent", "stat_replied", "stat_interested"])


class CampaignContact(models.Model):
    class CCStatus(models.TextChoices):
        PENDING   = "pending",   _("Ausstehend")
        SENT      = "sent",      _("Gesendet")
        FOLLOW_UP = "follow_up", _("Follow-up")
        REPLIED   = "replied",   _("Geantwortet")

    campaign   = models.ForeignKey(Campaign, on_delete=models.CASCADE,
                                    related_name="contacts", verbose_name=_("Kampagne"))
    contact    = models.ForeignKey(Contact, on_delete=models.CASCADE,
                                    related_name="campaign_contacts", verbose_name=_("Kontakt"))
    status     = models.CharField(max_length=20, choices=CCStatus.choices,
                                   default=CCStatus.PENDING, verbose_name=_("Status"))
    sent_at    = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    reply_text = models.TextField(blank=True)
    personalized_subject = models.CharField(max_length=300, blank=True)
    personalized_body    = models.TextField(blank=True)

    class Meta:
        unique_together = [("campaign", "contact")]
        verbose_name = _("Kampagnen-Kontakt")
        verbose_name_plural = _("Kampagnen-Kontakte")

    def __str__(self):
        return f"{self.campaign} -> {self.contact}"
