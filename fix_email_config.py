#!/usr/bin/env python
"""
Script to fix email configuration with correct credentials
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrmatcher.settings')
django.setup()

from hrapp.models import EmailConfiguration
from django.contrib.auth.models import User

def fix_email_config():
    print("=== FIXING EMAIL CONFIGURATION ===")
    
    # Get the user himanshu (ID: 2)
    try:
        user = User.objects.get(id=2, username='himanshu')
        print(f"Found user: {user.username} (ID: {user.id})")
        
        # Get the configuration
        config = EmailConfiguration.objects.get(user=user)
        print(f"Current config:")
        print(f"  Host: {config.email_host}")
        print(f"  Username: {config.email_username}")
        print(f"  Password length: {len(config.email_password)}")
        print(f"  Use TLS: {config.use_tls}")
        
        # Update with correct values based on successful test
        print("\nUpdating configuration with correct values...")
        config.email_username = 'prod@bharatcrest.com'
        # You'll need to provide the correct password here
        # config.email_password = 'your_correct_password_here'
        config.save()
        
        print("✅ Configuration updated!")
        print(f"New username: {config.email_username}")
        
        return True
        
    except User.DoesNotExist:
        print("❌ User not found")
        return False
    except EmailConfiguration.DoesNotExist:
        print("❌ Email configuration not found")
        return False

if __name__ == "__main__":
    fix_email_config()
