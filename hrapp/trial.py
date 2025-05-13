import imaplib
import socket
import ssl
import logging
import os
import imaplib
import email
from email.header import decode_header
from django.conf import settings
from django.core.files.storage import default_storage


logger = logging.getLogger(__name__)

def fetch_resumes_from_email():
    # Configuration
    IMAP_SERVER = getattr(settings, 'IMAP_SERVER', 'imap.secureserver.net')
    EMAIL = getattr(settings, 'IMAP_EMAIL', 'prod@bharatcrest.com')
    PASSWORD = getattr(settings, 'IMAP_PASSWORD', 'bharatcrest0711#')
    DOWNLOAD_DIR = r"C:\Users\himan\OneDrive\Documents\hrmatcher\media\resumes"

    print(f"\n=== Starting connection test ===")
    print(f"Server: {IMAP_SERVER}")
    print(f"Email: {EMAIL}")

    try:
        # Test 1: Basic network connectivity
        print("\n[1/4] Testing network reachability...")
        try:
            socket.create_connection((IMAP_SERVER.split(':')[0], 993), timeout=10)
            print("✓ Network connection successful")
        except socket.gaierror:
            raise Exception("✗ Could not resolve server address - check IMAP_SERVER")
        except socket.timeout:
            raise Exception("✗ Connection timed out - firewall blocking?")
        except ConnectionRefusedError:
            raise Exception("✗ Connection refused - server down or wrong port?")

        # Test 2: SSL handshake
        print("\n[2/4] Testing SSL handshake...")
        try:
            context = ssl.create_default_context()
            with socket.create_connection((IMAP_SERVER.split(':')[0], 993)) as sock:
                with context.wrap_socket(sock, server_hostname=IMAP_SERVER) as ssock:
                    print(f"✓ SSL established. Protocol: {ssock.version()}")
        except ssl.SSLCertVerificationError:
            raise Exception("✗ SSL certificate verification failed")
        except ssl.SSLError as e:
            raise Exception(f"✗ SSL error: {str(e)}")

        # Test 3: IMAP protocol
        print("\n[3/4] Testing IMAP protocol...")
        try:
            imap = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=10)
            print("✓ IMAP connection established")
            
            # Test 4: Authentication
            print("\n[4/4] Testing authentication...")
            try:
                response = imap.login(EMAIL, PASSWORD)
                if response[0] == 'OK':
                    print("✓ Login successful")
                    print(f"Server greeting: {imap.welcome.decode()}")
                    
                    # Rest of your processing code...
                    imap.select('INBOX')
                    # ... continue with your email processing ...
                    
                else:
                    raise Exception(f"Login failed: {response[1][0].decode()}")
            except imaplib.IMAP4.error as e:
                raise Exception(f"✗ Authentication failed: {str(e)}")
                
        except Exception as e:
            raise Exception(f"✗ IMAP connection failed: {str(e)}")

    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        print(f"\nERROR: {str(e)}")
        
        # Specific troubleshooting suggestions
        if "SSL" in str(e):
            print("→ Try adding: context = ssl._create_unverified_context()")
        elif "Authentication" in str(e):
            print("→ Check if you need an 'App Password' instead of your regular password")
            print("→ Verify email/password in your email client first")
        elif "resolve" in str(e):
            print("→ Try pinging the server: ping imap.secureserver.net")
        
        return False

    return True

fetch_resumes_from_email()