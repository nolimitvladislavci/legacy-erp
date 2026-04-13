"""Project forms — validation for project CRUD."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Project


class ProjectForm(forms.ModelForm):
    """Project create/edit form."""

    class Meta:
        model = Project
        fields = [
            "name",
            "description",
            "status",
            "client",
            "manager",
            "budget",
            "start_date",
            "end_date",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise ValidationError(_("Datum završetka ne može biti prije datuma početka."))
        return cleaned

    def clean_budget(self):
        budget = self.cleaned_data.get("budget")
        if budget is not None and budget < 0:
            raise ValidationError(_("Budžet ne može biti negativan."))
        return budget
