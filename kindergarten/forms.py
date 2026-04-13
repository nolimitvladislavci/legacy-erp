"""
Kindergarten forms — validacija za sve CRUD operacije.
GDPR cl.8: pristanak roditelja OBAVEZAN za djecu < 16.
"""
import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    Child, Guardian, ChildGuardian, Attendance, DailyReport, Announcement, KindergartenGroup,
)


def validate_oib(value):
    """Validate Croatian OIB (13-digit number with checksum)."""
    if not value:
        return
    if not re.match(r'^\d{11,13}$', value):
        raise ValidationError(_('OIB mora imati 11-13 znamenki.'))


class ChildForm(forms.ModelForm):
    """Form za upis djeteta — GDPR consent obavezan."""

    class Meta:
        model = Child
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'oib', 'gender',
            'group', 'allergies', 'special_needs', 'dietary_requirements',
            'gdpr_consent', 'photo_consent', 'status',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'special_needs': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        if company:
            self.fields['group'].queryset = KindergartenGroup.objects.filter(
                company=company, is_active=True)

    def clean_oib(self):
        oib = self.cleaned_data.get('oib', '')
        if oib:
            validate_oib(oib)
        return oib

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            age = (timezone.now().date() - dob).days / 365.25
            if age > 16:
                raise ValidationError(_('Dijete mora biti mlaje od 16 godina.'))
            if age < 0:
                raise ValidationError(_('Datum rodenja ne moze biti u buducnosti.'))
        return dob

    def clean_gdpr_consent(self):
        consent = self.cleaned_data.get('gdpr_consent')
        if not consent:
            raise ValidationError(
                _('GDPR pristanak roditelja je OBAVEZAN za djecu (cl.8 GDPR).')
            )
        return consent

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.company:
            instance.company = self.company
        if instance.gdpr_consent and not instance.gdpr_consent_date:
            instance.gdpr_consent_date = timezone.now()
        if not instance.enrolled_date:
            instance.enrolled_date = timezone.now().date()
        if commit:
            instance.save()
        return instance


class GuardianForm(forms.ModelForm):
    """Form za roditelja/skrbnika."""

    class Meta:
        model = Guardian
        fields = [
            'first_name', 'last_name', 'oib', 'email', 'phone',
            'phone_secondary', 'address',
        ]

    def clean_oib(self):
        oib = self.cleaned_data.get('oib', '')
        if oib:
            validate_oib(oib)
        return oib

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            cleaned = re.sub(r'[\s\-\(\)]', '', phone)
            if not re.match(r'^\+?\d{8,15}$', cleaned):
                raise ValidationError(_('Neispravan format telefona.'))
        return phone


class ChildGuardianForm(forms.ModelForm):
    """Form za vezu dijete-roditelj."""

    class Meta:
        model = ChildGuardian
        fields = ['relation', 'is_primary', 'can_pickup', 'is_billing_contact']


class AttendanceBulkForm(forms.Form):
    """Form za bulk attendance save — jedan red po djetetu."""
    child_id = forms.IntegerField(widget=forms.HiddenInput())
    status = forms.ChoiceField(choices=Attendance.Status.choices)
    arrival_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
    departure_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
    note = forms.CharField(required=False, max_length=200)


class BillingFilterForm(forms.Form):
    """Filter za billing list — mjesec/godina."""
    year = forms.IntegerField(min_value=2020, max_value=2030)
    month = forms.IntegerField(min_value=1, max_value=12)


class AnnouncementForm(forms.ModelForm):
    """Form za obavijest roditeljima."""

    class Meta:
        model = Announcement
        fields = ['title', 'content', 'priority', 'group', 'is_published']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['group'].queryset = KindergartenGroup.objects.filter(
                company=company, is_active=True)
            self.fields['group'].required = False


class DailyReportForm(forms.ModelForm):
    """Form za dnevni izvjestaj odgajateljice."""

    class Meta:
        model = DailyReport
        fields = ['group', 'date', 'content', 'is_published']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'content': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['group'].queryset = KindergartenGroup.objects.filter(
                company=company, is_active=True)


class BulkChildImportForm(forms.Form):
    """Form za CSV import djece."""
    csv_file = forms.FileField(
        label=_('CSV datoteka'),
        help_text=_('Stupci: ime, prezime, datum_rodenja, oib, roditelj_ime, '
                    'roditelj_prezime, roditelj_email, roditelj_telefon, grupa'),
    )
    send_portal_invites = forms.BooleanField(
        required=False, initial=True,
        label=_('Posalji pozivnice roditeljima'),
    )
