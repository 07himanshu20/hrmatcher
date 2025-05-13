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
    email_password = forms.CharField(widget=forms.PasswordInput())
    
    class Meta:
        model = EmailConfiguration
        fields = ['email_backend', 'email_host', 'email_port', 
                 'email_username', 'email_password', 'use_tls']