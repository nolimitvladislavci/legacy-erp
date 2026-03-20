"""Partner forms — validation for partner CRUD."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Partner


class PartnerForm(forms.ModelForm):
    """Partner create/edit form."""
    class Meta:
        model = Partner
        fields = [
            "name", "email", "phone", "address", "city",
            "zip_code", "country", "oib", "vat_id",
            "partner_type", "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 2:
            raise ValidationError(_("Ime partnera mora imati barem 2 znaka."))
        return name

    def clean_oib(self):
        oib = self.cleaned_data.get("oib", "").strip()
        if oib and len(oib) == 11 and not oib.isdigit():
            raise ValidationError(_("OIB mora imati 11 znamenki."))
        return oib

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()


class PartnerFilterForm(forms.Form):
    """Partner list filter form."""
    q = forms.CharField(required=False, label=_("Pretraži"))
    partner_type = forms.ChoiceField(
        choices=[("", _("Svi tipovi")), ("client", _("Klijent")), ("supplier", _("Dobavljač"))],
        required=False,
    )
