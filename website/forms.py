from django import forms

from .models import HitnaIntervencija


class HitnaIntervencijaForm(forms.ModelForm):
    class Meta:
        model = HitnaIntervencija
        fields = ["ime", "telefon", "email", "adresa", "grad", "drzava", "vrsta", "opis", "hitnost"]
        widgets = {
            "ime": forms.TextInput(attrs={"class": "form-control", "placeholder": "Vor- und Nachname"}),
            "telefon": forms.TextInput(attrs={"class": "form-control", "placeholder": "+49 ...", "type": "tel"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "email@beispiel.de"}),
            "adresa": forms.TextInput(attrs={"class": "form-control", "placeholder": "Straße und Hausnummer"}),
            "grad": forms.TextInput(attrs={"class": "form-control", "placeholder": "Stadt / PLZ"}),
            "drzava": forms.Select(
                attrs={"class": "form-select"},
                choices=[("DE", "Deutschland"), ("AT", "Österreich"), ("CH", "Schweiz"), ("HR", "Kroatien")],
            ),
            "vrsta": forms.Select(attrs={"class": "form-select"}),
            "opis": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Beschreiben Sie das Problem so genau wie möglich...",
                }
            ),
            "hitnost": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "ime": "Vor- und Nachname",
            "telefon": "Telefon (erforderlich)",
            "email": "E-Mail",
            "adresa": "Adresse",
            "grad": "Stadt / PLZ",
            "drzava": "Land",
            "vrsta": "Art des Notfalls",
            "opis": "Problembeschreibung",
            "hitnost": "Dringend — Ich benötige sofortige Hilfe",
        }
