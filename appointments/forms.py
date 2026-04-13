from django import forms

from .models import Appointment, BookingService, DossierEntry


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            "title",
            "client",
            "employee",
            "service",
            "resource",
            "start_time",
            "end_time",
            "appointment_type",
            "is_all_day",
            "status",
            "color",
            "description",
            "total_price",
            "payment_method",
        ]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "color": forms.TextInput(attrs={"type": "color"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        resource = cleaned_data.get("resource")
        if resource and start and end:
            overlapping = Appointment.objects.filter(
                resource=resource,
                start_time__lt=end,
                end_time__gt=start,
            )
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise forms.ValidationError("Upozorenje: Ovaj resurs je već zauzet u odabranom terminu.")
        return cleaned_data


class DossierEntryForm(forms.ModelForm):
    class Meta:
        model = DossierEntry
        fields = ["entry_type", "title", "content", "file", "structured_data", "appointment"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 4}),
            "structured_data": forms.HiddenInput(),
        }


class BookingServiceForm(forms.ModelForm):
    class Meta:
        model = BookingService
        fields = [
            "name",
            "description",
            "duration",
            "price",
            "resource_type",
            "branch_type",
            "slot_duration_minutes",
            "color",
            "icon",
            "is_active",
            "requires_dossier",
        ]
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
        }
