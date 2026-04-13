from django import forms

from .models import CompanyRegistration


class Step1CompanyForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        label='Company Name',
        widget=forms.TextInput(attrs={'class': 'reg-input', 'placeholder': 'Viskovic d.o.o.'})
    )
    oib = forms.CharField(
        max_length=20,
        label='OIB / Tax Number',
        widget=forms.TextInput(attrs={'class': 'reg-input', 'placeholder': '12345678901'})
    )
    country = forms.ChoiceField(
        label='Country',
        choices=[
            ('Croatia', 'Croatia'),
            ('Germany', 'Germany'),
            ('Austria', 'Austria'),
            ('Slovenia', 'Slovenia'),
            ('Bosnia', 'Bosnia & Herzegovina'),
            ('Serbia', 'Serbia'),
            ('Other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'reg-input'})
    )
    business_type = forms.ChoiceField(
        label='Business Type',
        choices=CompanyRegistration.BUSINESS_TYPES,
        widget=forms.Select(attrs={'class': 'reg-input'})
    )
    address = forms.CharField(
        label='Business Address',
        widget=forms.Textarea(attrs={'class': 'reg-input', 'rows': 3, 'placeholder': 'Street, City, ZIP'})
    )
    contact_name = forms.CharField(
        max_length=200,
        label='Contact Person',
        widget=forms.TextInput(attrs={'class': 'reg-input', 'placeholder': 'John Smith'})
    )
    contact_email = forms.EmailField(
        label='Contact Email',
        widget=forms.EmailInput(attrs={'class': 'reg-input', 'placeholder': 'john@company.com'})
    )
    contact_phone = forms.CharField(
        max_length=50,
        label='Contact Phone',
        widget=forms.TextInput(attrs={'class': 'reg-input', 'placeholder': '+49 123 456789'})
    )

    def clean_oib(self):
        oib = self.cleaned_data['oib'].strip()
        if CompanyRegistration.objects.filter(oib=oib).exclude(status='rejected').exists():
            raise forms.ValidationError('A registration with this OIB already exists.')
        return oib


class Step2DocumentForm(forms.Form):
    document = forms.FileField(
        label='Company Registration Document',
        required=False,
        widget=forms.FileInput(attrs={'class': 'reg-file-input', 'accept': '.pdf,.jpg,.jpeg,.png'})
    )

    def clean_document(self):
        doc = self.cleaned_data.get('document')
        if doc:
            max_size = 10 * 1024 * 1024  # 10MB
            if doc.size > max_size:
                raise forms.ValidationError('File too large. Maximum size is 10MB.')
            allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
            if hasattr(doc, 'content_type') and doc.content_type not in allowed_types:
                raise forms.ValidationError('Only PDF, JPG, and PNG files are allowed.')
        return doc


class Step3PlanForm(forms.Form):
    selected_plan = forms.ChoiceField(
        choices=[
            ('starter', 'Starter'),
            ('business', 'Business'),
            ('enterprise', 'Enterprise'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'plan-radio'})
    )
