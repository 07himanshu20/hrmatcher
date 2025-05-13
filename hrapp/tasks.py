from __future__ import absolute_import
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrmatcher.settings')

import imaplib
import email
import logging
from datetime import datetime, timedelta
from email.header import decode_header
from typing import List, Dict, Any, Optional, Union

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
import imaplib
import email
from email.header import decode_header
import os
from datetime import datetime

# hrapp/tasks.py
import os
import imaplib
import email
from email.header import decode_header
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)
from .models import EmailConfiguration
@shared_task(bind=True)

def fetch_resumes_from_email(self, user_id):
        
    

    # Configuration
    config = EmailConfiguration.objects.get(user_id=user_id)
    IMAP_SERVER = config.email_host
    EMAIL = config.email_username
    PASSWORD = config.email_password
    PORT = config.email_port
    USE_TLS = config.use_tls
    DOWNLOAD_DIR = r"C:\Users\himan\OneDrive\Documents\hrmatcher\media\resumes"
    RESUME_KEYWORDS = ["resume", "cv", "application", "apply", "applying"]

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    saved_files = []

    try:
        logger.info("Connecting to IMAP...")
        with imaplib.IMAP4_SSL(IMAP_SERVER, 993) as imap:
            imap.login(EMAIL, PASSWORD)
            logger.info("Logged in successfully")

            status, _ = imap.select("INBOX")  # IMPORTANT: remove readonly=True
            if status != 'OK':
                raise Exception("Failed to select INBOX")

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