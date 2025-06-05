from django import forms
from .models import JobRequirement
from .models import EmailConfiguration
# forms.py
class JobRequirementForm(forms.ModelForm):
    class Meta:
        model = JobRequirement
        fields = ['position', 'skills', 'min_experience']
        widgets = {
            'skills': forms.TextInput(attrs={
                'placeholder': 'Python, Django, AWS'
            })
        }
        
class EmailConfigurationForm(forms.ModelForm):
    # Override all fields to ensure they're always empty
    email_backend = forms.CharField(
        required=True,
        widget=forms.Select(choices=[
            ('', 'Select protocol...'),
            ('django.core.mail.backends.smtp.EmailBackend', 'SMTP (For sending emails)'),
            ('django.core.mail.backends.imap.EmailBackend', 'IMAP (For fetching emails)')
        ])
    )
    
    email_host = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': 'e.g. smtp.gmail.com'})
    )
    
    email_port = forms.IntegerField(
        required=True,
        widget=forms.NumberInput(attrs={'autocomplete': 'off', 'placeholder': 'e.g. 587, 465, 993'})
    )
    
    email_username = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )
    
    email_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'render_value': False}),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Always clear these fields regardless of the instance data
        self.initial['email_backend'] = ''
        self.initial['email_host'] = ''
        self.initial['email_port'] = ''
        self.initial['email_username'] = ''
        self.initial['email_password'] = ''
        self.initial['use_tls'] = False
    
    class Meta:
        model = EmailConfiguration
        fields = ['email_backend', 'email_host', 'email_port', 
                 'email_username', 'email_password', 'use_tls']
