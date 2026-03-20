from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class ProjectLead(models.Model):

    class Status(models.TextChoices):
        NOVI_UPIT          = 'NOVI_UPIT',          _('Novi upit')
        INTERNA_PROCJENA   = 'INTERNA_PROCJENA',   _('Interna procjena')
        NA_BURZI           = 'NA_BURZI',           _('Na burzi')
        PREUZETO           = 'PREUZETO',           _('Preuzeto')
        RIJESENO           = 'RIJESENO',           _('Riješeno')

    class Category(models.TextChoices):
        KUPAONICA  = 'kupaonica',  _('Kupaonica')
        PLOCICE    = 'plocice',    _('Pločice')
        VODOINSTAL = 'vodoinstal', _('Vodoinstalacije')
        ELEKTRIKA  = 'elektrika',  _('Elektrika')
        GRIJANJE   = 'grijanje',   _('Grijanje')
        RENOVACIJA = 'renovacija', _('Renovacija')
        GRADNJA    = 'gradnja',    _('Gradnja')
        FASADA     = 'fasada',     _('Fasada')
        OSTALO     = 'ostalo',     _('Ostalo')

    company       = models.ForeignKey('companies.Company', on_delete=models.CASCADE,
                                       related_name='project_leads', null=True, blank=True)
    title         = models.CharField(max_length=200)
    description   = models.TextField()
    category      = models.CharField(max_length=30, choices=Category.choices, default=Category.OSTALO)
    location      = models.CharField(max_length=200)
    budget_from   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_to     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desired_start = models.DateField(null=True, blank=True)
    contact_name  = models.CharField(max_length=100)
    contact_phone = models.CharField(max_length=30)
    contact_email = models.EmailField(blank=True)
    status        = models.CharField(max_length=20, choices=Status.choices,
                                      default=Status.NOVI_UPIT, db_index=True)
    assigned_to   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='assigned_leads')
    internal_notes= models.TextField(blank=True)
    is_public     = models.BooleanField(default=False)
    taken_by      = models.ForeignKey('companies.Company', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='taken_leads')
    taken_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='taken_leads')
    taken_at      = models.DateTimeField(null=True, blank=True)
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='created_leads')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Projektni upit'
        verbose_name_plural = 'Projektni upiti'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.title} – {self.get_status_display()}'

    @property
    def budget_display(self):
        def _fmt(val):
            return f'{val:,.0f}'.replace(',', '.')
        if self.budget_from and self.budget_to:
            return f'€{_fmt(self.budget_from)} – €{_fmt(self.budget_to)}'
        elif self.budget_from:
            return f'od €{_fmt(self.budget_from)}'
        return '–'


class LeadActivity(models.Model):
    lead       = models.ForeignKey(ProjectLead, on_delete=models.CASCADE, related_name='activities')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action     = models.CharField(max_length=200)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    note       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.lead.title} – {self.action}'
