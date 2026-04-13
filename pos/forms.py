"""POS forms — validation for terminal, session, receipt operations."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django.db import DatabaseError, IntegrityError

from .models import POSPaymentLine, POSTerminal


class TerminalForm(forms.ModelForm):
    """Terminal creation/edit form."""
    class Meta:
        model = POSTerminal
        fields = ["name", "location", "is_active"]


class OpenSessionForm(forms.Form):
    """Form for opening a POS session."""
    opening_cash = forms.DecimalField(
        min_value=Decimal("0"), initial=Decimal("0"),
        label=_("Početni iznos u blagajni"),
    )


class CloseSessionForm(forms.Form):
    """Form for closing a POS session."""
    closing_cash = forms.DecimalField(
        min_value=Decimal("0"), initial=Decimal("0"),
        label=_("Završni iznos u blagajni"),
    )


class AddItemForm(forms.Form):
    """Form for adding item to receipt."""
    inventory_item_id = forms.IntegerField(required=False)
    description = forms.CharField(max_length=200)
    quantity = forms.DecimalField(min_value=Decimal("0.01"), initial=Decimal("1"))
    unit_price = forms.DecimalField(min_value=Decimal("0"))
    unit = forms.CharField(max_length=20, initial="kom")
    tax_rate = forms.DecimalField(initial=Decimal("25"))
    discount_percent = forms.DecimalField(initial=Decimal("0"), min_value=Decimal("0"), max_value=Decimal("100"))

    def clean_description(self):
        return self.cleaned_data["description"].strip()[:200]


class PaymentForm(forms.Form):
    """Form for processing payment."""
    payment_method = forms.ChoiceField(choices=POSPaymentLine.Method.choices)
    amount_paid = forms.DecimalField(min_value=Decimal("0"))

    def clean_amount_paid(self):
        amount = self.cleaned_data["amount_paid"]
        if amount <= 0:
            raise ValidationError(_("Iznos plaćanja mora biti veći od 0."))
        return amount


class InventoryCSVImportForm(forms.Form):
    """Form for CSV inventory import."""
    csv_file = forms.FileField(
        label=_("CSV datoteka"),
        help_text=_("Format: naziv, cijena, PDV, barkod, kategorija"),
    )

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.endswith((".csv", ".CSV")):
            raise ValidationError(_("Samo CSV datoteke su dopuštene."))
        if f.size > 5 * 1024 * 1024:
            raise ValidationError(_("Datoteka ne smije biti veća od 5MB."))
        return f
