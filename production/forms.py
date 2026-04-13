"""
production/forms.py — Django ModelForms + inline formsets for BOM & Orders.
"""

from django import forms
from django.forms import inlineformset_factory

from inventory.models import InventoryItem

from .models import (
    BillOfMaterials,
    BOMLine,
    ProductionOrder,
    QualityCheck,
    Workstation,
)


class WorkstationForm(forms.ModelForm):
    class Meta:
        model = Workstation
        fields = [
            "name",
            "code",
            "ws_type",
            "status",
            "capacity_per_hour",
            "hourly_cost",
            "location",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "ws_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "capacity_per_hour": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "hourly_cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class BillOfMaterialsForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterials
        fields = [
            "name",
            "code",
            "output_item",
            "output_quantity",
            "output_unit",
            "version",
            "status",
            "default_workstation",
            "estimated_duration_minutes",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "output_item": forms.Select(attrs={"class": "form-select"}),
            "output_quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "output_unit": forms.TextInput(attrs={"class": "form-control"}),
            "version": forms.NumberInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "default_workstation": forms.Select(attrs={"class": "form-select"}),
            "estimated_duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["output_item"].queryset = InventoryItem.objects.filter(company=company).order_by("name")
            self.fields["default_workstation"].queryset = Workstation.objects.filter(company=company, status="active")
            self.fields["default_workstation"].required = False


class BOMLineForm(forms.ModelForm):
    class Meta:
        model = BOMLine
        fields = ["item", "quantity", "unit", "waste_percent", "sort_order", "notes"]
        widgets = {
            "item": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.0001"}),
            "unit": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "waste_percent": forms.NumberInput(attrs={"class": "form-control form-control-sm", "step": "0.01"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control form-control-sm"}),
            "notes": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        }


def get_bomline_formset(company=None, **kwargs):
    """Return a BOMLine inline formset, scoped to company items."""
    BOMLineFormSet = inlineformset_factory(
        BillOfMaterials,
        BOMLine,
        form=BOMLineForm,
        extra=1,
        can_delete=True,
    )
    formset = BOMLineFormSet(**kwargs)
    if company:
        item_qs = InventoryItem.objects.filter(company=company).order_by("name")
        for form in formset.forms:
            form.fields["item"].queryset = item_qs
    return formset


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = [
            "bom",
            "planned_quantity",
            "priority",
            "workstation",
            "planned_start",
            "planned_end",
            "status",
            "batch_number",
            "lot_number",
            "expiry_date",
            "notes",
        ]
        widgets = {
            "bom": forms.Select(attrs={"class": "form-select"}),
            "planned_quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "workstation": forms.Select(attrs={"class": "form-select"}),
            "planned_start": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "planned_end": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "batch_number": forms.TextInput(attrs={"class": "form-control"}),
            "lot_number": forms.TextInput(attrs={"class": "form-control"}),
            "expiry_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    # For new orders, auto-fill order_number in the view (not editable via form)
    order_number = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
        required=False,
    )

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["bom"].queryset = BillOfMaterials.objects.filter(
                company=company, status="active"
            ).select_related("output_item")
            self.fields["workstation"].queryset = Workstation.objects.filter(company=company, status="active")
            self.fields["workstation"].required = False
        # Status limited on create
        if not self.instance.pk:
            self.fields["status"].choices = [
                ("draft", "Nacrt"),
                ("confirmed", "Potvrđen"),
            ]


class QualityCheckForm(forms.ModelForm):
    class Meta:
        model = QualityCheck
        fields = [
            "check_name",
            "parameter",
            "expected_value",
            "actual_value",
            "tolerance",
            "result",
            "step",
            "notes",
        ]
        widgets = {
            "check_name": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "parameter": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "expected_value": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "actual_value": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "tolerance": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "result": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "step": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "notes": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2}),
        }

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        if order:
            self.fields["step"].queryset = order.steps.all()
            self.fields["step"].required = False
