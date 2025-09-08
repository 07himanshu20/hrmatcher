#!/usr/bin/env python
"""
Debug script to check email configuration in the database
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrmatcher.settings')
django.setup()

from hrapp.models import EmailConfiguration
from django.contrib.auth.models import User

def debug_email_config():
    print("=== EMAIL CONFIGURATION DEBUG ===")
    
    # Get all users
    users = User.objects.all()
    print(f"Total users: {users.count()}")
    
    for user in users:
        print(f"\nUser: {user.username} (ID: {user.id})")
        
        try:
            config = EmailConfiguration.objects.get(user_id=user.id)
            print(f"  Email Host: {config.email_host}")
            print(f"  Email Port: {config.email_port}")
            print(f"  Email Username: {config.email_username}")
            print(f"  Password exists: {bool(config.email_password)}")
            print(f"  Password length: {len(config.email_password) if config.email_password else 0}")
            print(f"  Use TLS: {config.use_tls}")
            print(f"  Created: {config.created_at}")
            print(f"  Updated: {config.updated_at}")
            
            # Show first few chars of password for debugging (masked)
            if config.email_password:
                masked_pwd = config.email_password[:3] + "*" * max(0, len(config.email_password) - 3)
                print(f"  Password preview: {masked_pwd}")
                # Check if it looks like it might be hashed
                if len(config.email_password) > 20 and ('$' in config.email_password or config.email_password.startswith('sha') or config.email_password.startswith('pbkdf2')):
                    print("  WARNING: Password looks like it might be hashed!")
            else:
                print(f"  Password: EMPTY!")
                
        except EmailConfiguration.DoesNotExist:
            print(f"  No email configuration found for user {user.username}")
    
    print("\n=== ALL EMAIL CONFIGURATIONS ===")
    all_configs = EmailConfiguration.objects.all().order_by('-updated_at')
    print(f"Total configurations: {all_configs.count()}")
    
    for config in all_configs:
        print(f"Config ID {config.id}: User {config.user.username} ({config.user.id}), Host: {config.email_host}, Updated: {config.updated_at}")
        print(f"  Username: {config.email_username}, Password length: {len(config.email_password) if config.email_password else 0}")
    
    # Show the most recent configuration details
    if all_configs.exists():
        latest = all_configs.first()
        print(f"\n=== LATEST CONFIGURATION ===")
        print(f"User: {latest.user.username} (ID: {latest.user.id})")
        print(f"Host: {latest.email_host}")
        print(f"Username: {latest.email_username}")
        print(f"Password first 10 chars: {latest.email_password[:10] if latest.email_password else 'EMPTY'}")
        print(f"Updated: {latest.updated_at}")

if __name__ == "__main__":
    debug_email_config()
