"""
Invoicing forms — Django form validation for invoices and items.

Replaces 40+ request.POST.get() calls with validated, type-safe forms.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Invoice, InvoiceItem


class InvoiceForm(forms.ModelForm):
    """Main invoice form for create/edit."""

    class Meta:
        model = Invoice
        fields = [
            "doctype", "country", "status",
            "date_issued", "date_due", "date_delivery",
            "client_name", "client_address", "client_city",
            "client_country", "client_oib", "client_email",
            "payment_method", "currency", "iban", "swift",
            "reference_number", "note", "internal_note",
            "nkd_code",
        ]
        widgets = {
            "date_issued": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "date_due": forms.DateInput(attrs={"type": "date"}),
            "date_delivery": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
            "internal_note": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_date_due(self):
        due = self.cleaned_data.get("date_due")
        issued = self.cleaned_data.get("date_issued")
        if due and issued and due < issued.date():
            raise ValidationError(
                _("Datum dospijeća ne može biti prije datuma izdavanja.")
            )
        return due

    def clean_client_oib(self):
        oib = self.cleaned_data.get("client_oib", "").strip()
        if oib and len(oib) == 11 and not oib.isdigit():
            raise ValidationError(_("OIB mora sadržavati 11 znamenki."))
        return oib

    def clean_iban(self):
        iban = self.cleaned_data.get("iban", "").strip().replace(" ", "")
        if iban and len(iban) < 15:
            raise ValidationError(_("IBAN je prekratak."))
        return iban.upper()


class InvoiceItemForm(forms.ModelForm):
    """Single invoice item form."""

    class Meta:
        model = InvoiceItem
        fields = [
            "description", "quantity", "unit",
            "unit_price", "discount", "tax_rate",
        ]

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is not None and qty <= 0:
            raise ValidationError(_("Količina mora biti veća od 0."))
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get("unit_price")
        if price is not None and price < 0:
            raise ValidationError(_("Cijena ne može biti negativna."))
        return price

    def clean_discount(self):
        disc = self.cleaned_data.get("discount")
        if disc is not None and (disc < 0 or disc > 100):
            raise ValidationError(_("Popust mora biti između 0% i 100%."))
        return disc


class InvoiceItemFormSet(forms.BaseInlineFormSet):
    """Validates that invoice has at least one item."""

    def clean(self):
        super().clean()
        valid_forms = [
            f for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]
        if not valid_forms:
            raise ValidationError(_("Račun mora imati barem jednu stavku."))


InvoiceItemInlineFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    formset=InvoiceItemFormSet,
    extra=1,
    can_delete=True,
)


class QuickInvoiceForm(forms.Form):
    """Simplified form for quick invoice creation (wizard)."""

    doctype = forms.ChoiceField(choices=Invoice.DOCTYPE_CHOICES, initial="R")
    country = forms.ChoiceField(choices=Invoice.COUNTRY_CHOICES, initial="HR")
    client_name = forms.CharField(max_length=200)
    client_oib = forms.CharField(max_length=30, required=False)
    client_email = forms.EmailField(required=False)
    payment_method = forms.ChoiceField(choices=Invoice.PAYMENT_CHOICES, initial="bank")
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def clean_client_name(self):
        name = self.cleaned_data["client_name"].strip()
        if len(name) < 2:
            raise ValidationError(_("Ime klijenta je prekratko."))
        return name


class InvoiceFilterForm(forms.Form):
    """Form for invoice list filtering."""

    STATUS_CHOICES = [("", _("Svi statusi"))] + Invoice.STATUS_CHOICES
    DOCTYPE_CHOICES = [("", _("Sve vrste"))] + Invoice.DOCTYPE_CHOICES

    q = forms.CharField(required=False, label=_("Pretraži"))
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False)
    doctype = forms.ChoiceField(choices=DOCTYPE_CHOICES, required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
