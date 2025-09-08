from __future__ import absolute_import
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrmatcher.settings')

import imaplib
import email
import email.utils
import logging
import tempfile
from datetime import datetime, timedelta
from email.header import decode_header
from typing import List, Dict, Any, Optional, Union
import ssl

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="hrapp.tasks.process_resumes_from_email")
def process_resumes_from_email(self, job_req_id):
    """Process resumes from email with proper model imports"""
    # Import models inside the task to avoid circular imports
    from hrapp.models import JobRequirement, Candidate
    from hrapp.utils import (
        extract_text_from_resume,
        extract_name_from_resume,
        extract_skills_from_resume,
        calculate_match_score
    )
    
    try:
        job_req = JobRequirement.objects.get(id=job_req_id)
        resume_files = fetch_resumes_from_email()
        
        if not resume_files:
            logger.info("No resumes found in email")
            return {"status": "completed", "message": "No resumes found"}
        
        matched_candidates = []
        total_files = len(resume_files)
        
        for i, resume_path in enumerate(resume_files, 1):
            try:
                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_files,
                        'percent': int(i * 100 / total_files),
                        'file': os.path.basename(resume_path)
                    }
                )
                
                # Process resume
                text = extract_text_from_resume(resume_path)
                if not text:
                    continue
                    
                name = extract_name_from_resume(text)
                skills = extract_skills_from_resume(text)
                score = calculate_match_score(skills, job_req.skills)
                
                # Create candidate record
                rel_path = os.path.relpath(resume_path, settings.MEDIA_ROOT)
                Candidate.objects.create(
                    name=name,
                    resume=rel_path,
                    score=score,
                    matched_skills=", ".join(
                        skill for skill in job_req.get_skills_list() 
                        if skill in skills
                    ),
                    matched=score >= job_req.min_score
                )
                
                matched_candidates.append({
                    'name': name,
                    'resume': os.path.basename(resume_path),
                    'score': score
                })
                    
            except Exception as e:
                logger.error(f"Failed to process {resume_path}: {str(e)}")
                continue
        
        cache.set(f'matched_{job_req_id}', matched_candidates, timeout=3600)
        return {
            'status': 'completed',
            'matched': len(matched_candidates),
            'total_processed': total_files
        }
        
    except JobRequirement.DoesNotExist:
        return {"status": "failed", "error": f"JobRequirement {job_req_id} not found"}
    except Exception as e:
        logger.exception("Resume processing task failed")
        self.retry(exc=e, countdown=60, max_retries=3)

# hrapp/tasks.py
import os
import imaplib
import email
from email.header import decode_header
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)
from .models import EmailConfiguration

def fetch_resumes_from_email(user_id, date_from=None, date_to=None):
    # Configuration
    logger.info(f"Attempting to fetch email config for user_id: {user_id}")
    try:
        config = EmailConfiguration.objects.get(user_id=user_id)
        logger.info(f"Found email config for user_id {user_id}: username={config.email_username}")
    except EmailConfiguration.DoesNotExist:
        logger.error(f"Email configuration not found for user_id: {user_id}")
        raise Exception("Email configuration not found. Please configure your email settings first.")
    
    IMAP_SERVER = config.email_host
    EMAIL = config.email_username
    PASSWORD = config.email_password
    PORT = config.email_port
    USE_TLS = config.use_tls
    
    # Debug logging
    logger.info(f"Email configuration - Host: {IMAP_SERVER}, Username: {EMAIL}, Port: {PORT}, TLS: {USE_TLS}")
    logger.info(f"Password present: {bool(PASSWORD)}, Password length: {len(PASSWORD) if PASSWORD else 0}")
    
    if not PASSWORD:
        logger.error("Email password is empty! Please check your email configuration.")
        raise Exception("Email password is not configured. Please update your email settings.")
    
    # Import settings and os at the beginning of the function
    from django.conf import settings
    import os
    
    # Log the base directory and media root for debugging
    logger.info(f"BASE_DIR: {settings.BASE_DIR}")
    logger.info(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
    
    # Create a user-specific directory for resumes
    user_resume_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')

    
    # Log the directory we're trying to create
    logger.info(f"Attempting to create directory: {user_resume_dir}")
    
    try:
        os.makedirs(user_resume_dir, exist_ok=True)
        logger.info(f"Directory created successfully: {user_resume_dir}")
    except Exception as e:
        logger.error(f"Error creating directory: {str(e)}")
        # Fallback to a temporary directory
        import tempfile
        user_resume_dir = tempfile.mkdtemp()
        logger.info(f"Using temporary directory instead: {user_resume_dir}")
    
    DOWNLOAD_DIR = user_resume_dir
    
    RESUME_KEYWORDS = ["resume","job","availability" "cv", "application", "apply","intern", "internship", "applying","interview"]

    saved_files = []

    try:
        logger.info("Connecting to IMAP...")
        # Always use a fresh SSL context for each connection
        ssl_context = ssl.create_default_context()
        with imaplib.IMAP4_SSL(IMAP_SERVER, 993, ssl_context=ssl_context) as imap:
            imap.login(EMAIL, PASSWORD)
            logger.info("Logged in successfully")

            status, _ = imap.select("INBOX")  # IMPORTANT: remove readonly=True
            if status != 'OK':
                raise Exception("Failed to select INBOX")

            # Build search criteria with date filtering - ONLY fetch emails in specified date range
            search_criteria = []
            
            # Add date filtering if provided - this filters at IMAP level, not after fetching
            if date_from:
                try:
                    # Convert date string to IMAP format (DD-Mon-YYYY)
                    from_date = datetime.strptime(date_from, '%Y-%m-%d')
                    formatted_from_date = from_date.strftime('%d-%b-%Y')
                    search_criteria.append(f'SINCE {formatted_from_date}')
                    logger.info(f"IMAP filtering emails FROM: {formatted_from_date}")
                except ValueError:
                    logger.warning(f"Invalid from_date format: {date_from}")
            
            if date_to:
                try:
                    # Convert date string to IMAP format (DD-Mon-YYYY)
                    # For BEFORE, we need the day AFTER to_date since BEFORE is exclusive
                    to_date = datetime.strptime(date_to, '%Y-%m-%d')
                    # Add one day to make BEFORE inclusive of the to_date
                    to_date_inclusive = to_date + timedelta(days=1)
                    formatted_to_date = to_date_inclusive.strftime('%d-%b-%Y')
                    search_criteria.append(f'BEFORE {formatted_to_date}')
                    logger.info(f"IMAP filtering emails TO: {date_to} (using BEFORE {formatted_to_date})")
                except ValueError:
                    logger.warning(f"Invalid to_date format: {date_to}")
            
            # Perform IMAP search - this ONLY returns emails within the date range, no other emails are fetched
            if search_criteria:
                # Join criteria with space for IMAP search - this filters at server level
                search_query = ' '.join(search_criteria)
                logger.info(f"IMAP search query (server-side filtering): '{search_query}'")
                status, messages = imap.search(None, search_query)
                logger.info("Only fetching emails that match the date criteria - no other emails will be downloaded")
            else:
                logger.info("No date filtering specified - will fetch ALL emails")
                status, messages = imap.search(None, 'ALL')
            if status != 'OK':
                raise Exception("IMAP search failed")

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} emails to scan")

            for email_id in email_ids:
                try:
                    status, msg_data = imap.fetch(email_id, "(RFC822)")
                    if status != 'OK':
                        logger.warning(f"Fetch failed for email {email_id}")
                        continue

                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = msg.get("Subject", "")
                    subject_lower = subject.lower()
                    
                    # Check if email subject contains resume keywords
                    if not any(keyword in subject_lower for keyword in RESUME_KEYWORDS):
                        logger.debug(f"Skipping non-resume email: {subject[:50]}...")
                        continue

                    logger.info(f"Processing resume email: {subject}")

                    for part in msg.walk():
                        if part.get_content_disposition() != 'attachment':
                            continue

                        filename = part.get_filename()
                        if not filename:
                            continue

                        filename = decode_header(filename)[0][0]
                        if isinstance(filename, bytes):
                            filename = filename.decode(errors="ignore")

                        if not filename.lower().endswith(('.pdf', '.docx')):
                            continue

                        payload = part.get_payload(decode=True)
                        if payload:
                            filepath = os.path.join(DOWNLOAD_DIR, filename)
                            with open(filepath, 'wb') as f:
                                f.write(payload)

                            saved_files.append(filepath)
                            logger.info(f"Saved resume: {filepath}")
                        else:
                            logger.warning(f"Attachment {filename} has no payload")

                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {str(e)}")
                    continue

        return saved_files

    except Exception as e:
        logger.error(f"IMAP operation failed: {str(e)}")
        raise



def cleanup_old_files(days: int = 7) -> Dict[str, Union[int, str]]:
    """Clean up old resume files"""
    try:
        cutoff = datetime.now() - timedelta(days=days)
        deleted_count = 0
        resumes_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
        
        if not os.path.exists(resumes_dir):
            return {'status': 'skipped', 'message': 'Directory not found'}
        
        for filename in os.listdir(resumes_dir):
            filepath = os.path.join(resumes_dir, filename)
            try:
                if os.path.getmtime(filepath) < cutoff.timestamp():
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"Deleted old file: {filename}")
            except Exception as e:
                logger.error(f"Couldn't delete {filename}: {str(e)}")
                continue
        
        return {
            'status': 'completed',
            'deleted': deleted_count,
            'retention_days': days
        }
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


