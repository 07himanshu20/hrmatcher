import logging
import os
import re
import time
import json
import warnings
from typing import List, Dict, Any, Union
from PyPDF2 import PdfReader
from docx import Document
import pdfplumber
import google.generativeai as genai
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential
import imaplib  # For IMAP connection testing
import smtplib  # For SMTP connection testing
import logging  # For error logging
from typing import Tuple  # For type hints (optional but recommended)

# If you want to add detailed error handling:
from socket import timeout as socket_timeout
from ssl import SSLError
from imaplib import IMAP4_SSL, IMAP4
from smtplib import SMTP, SMTP_SSL, SMTPException


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to INFO in production

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)  # Set to INFO in production
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(
    'gemini-1.5-pro',
    generation_config={
        'temperature': 0.1,
        'max_output_tokens': 500,
        'top_p': 0.3
    },
    safety_settings={
        'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
        'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE'
    }
)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_with_gemini(prompt: str) -> str:
    """Protected API call with rate limiting"""
    try:
        response = gemini_model.generate_content(prompt)
        return response.text if response.text else ""
    except Exception as e:
        if "quota" in str(e).lower():
            time.sleep(5)  # Additional delay for quota issues
        raise

def extract_text_from_resume(filepath: str) -> str:
    """Robust text extraction with multiple fallbacks"""
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
                
        elif ext == '.pdf':
            # Try pdfplumber first
            try:
                with pdfplumber.open(filepath) as pdf:
                    return "\n".join(page.extract_text() or "" for page in pdf.pages)
            except Exception:
                with open(filepath, 'rb') as f:
                    return " ".join(page.extract_text() or "" for page in PdfReader(f).pages)
                    
        elif ext == '.docx':
            return " ".join(p.text for p in Document(filepath).paragraphs if p.text)
            
        else:
            raise ValueError(f"Unsupported file type: {filepath}")
            
    except Exception as e:
        warnings.warn(f"Error extracting text: {str(e)}")
        return ""
    
    
    
def extract_skills_from_resume(file_path: str, skills_to_find: List[str]) -> List[str]:
    """
    Extract matching skills from resume
    
    Args:
        file_path: Path to resume file
        skills_to_find: List of skills to search for
        
    Returns:
        List of matched skills
    """
    try:
        text = extract_text_from_resume(file_path)
        if not text:
            return []
            
        # Normalize cases for comparison
        text_lower = text.lower()
        skills_lower = [s.lower() for s in skills_to_find]
        
        # Find exact matches
        matched_skills = [
            skills_to_find[i] 
            for i, skill in enumerate(skills_lower) 
            if skill in text_lower
        ]
        
        return matched_skills
        
    except Exception as e:
        print(f"Error extracting skills from {file_path}: {str(e)}")
        return []
    
    
def extract_experience(text: str) -> float:
    """Extract years of experience"""
    patterns = [
        r'(\d+)\s*(?:years?|yrs?)(?:\s*\+?)?\s*experience',
        r'experience\s*:\s*(\d+)\s*years?',
        r'(\d+)\s*-\s*(\d+)\s*years'
    ]
    for pattern in patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            return float(max(match.groups()))
    return 0.0



def get_resume_files() -> List[str]:
    """Get all resume files from media directory"""
    resume_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
    if not os.path.exists(resume_dir):
        os.makedirs(resume_dir, exist_ok=True)
    return [
        os.path.join(resume_dir, f) 
        for f in os.listdir(resume_dir) 
        if f.lower().endswith(('.pdf', '.docx'))
    ]


from typing import List, Union, Tuple



def calculate_match_score(
    resume_skills: List[str],
    job_skills: List[str],
    min_experience: int,
    resume_experience: Union[int, float]
) -> Tuple[float, List[str], List[str]]:
    """
    Enhanced match scoring with detailed skill tracking
    
    Args:
        resume_skills: List of skills from resume (case insensitive)
        job_skills: List of required skills (case sensitive)
        min_experience: Minimum years required
        resume_experience: Candidate's experience
        
    Returns:
        tuple: (score, matched_skills, missing_skills)
        - score: float (0-100)
        - matched_skills: List[str] (specific matched skills)
        - missing_skills: List[str] (required but not found)
    """
    # Normalize skill cases for comparison
    resume_skills_lower = [s.lower() for s in resume_skills]
    job_skills_lower = [s.lower() for s in job_skills]
    
    # Find exact matches preserving original case
    matched_skills = [
        job_skills[i] 
        for i, skill in enumerate(job_skills_lower) 
        if skill in resume_skills_lower
    ]
    
    missing_skills = [
        skill 
        for skill in job_skills 
        if skill.lower() not in resume_skills_lower
    ]
    
    # Calculate skill match (50% weight)
    skill_match = (len(matched_skills) / len(job_skills)) * 50 if job_skills else 0
    
    # Calculate experience match (50% weight)
    exp_match = 0.0
    if resume_experience >= min_experience:
        exp_match = 50 * min(1.0, resume_experience / max(min_experience, 1))
    
    # Combine scores
    total_score = max(0.0, min(100.0, round(skill_match + exp_match, 1)))
    
    return total_score, matched_skills, missing_skills

import re
from typing import Dict, Any, List, Optional
import dateparser
from datetime import datetime

def extract_candidate_info(text: str) -> Dict[str, Any]:
    """
    Extract structured candidate information from resume text
    
    Returns:
        {
            'name': str,
            'email': Optional[str],
            'phone': Optional[str],
            'experience': float,
            'skills': List[str],
            'education': List[str]
        }
    """
    return {
        'name': extract_name_from_resume(text),
        'email': extract_email_from_resume(text),
        'phone': extract_phone(text),
        'experience': calculate_total_experience(text),
        'skills': extract_skills_section(text),
        'education': extract_education(text)
    }

def extract_name_from_resume(text: str) -> str:
    """Extract candidate name using multi-method approach"""
    # Method 1: First line that looks like a name
    for line in text.split('\n'):
        line = line.strip()
        if (2 <= len(line.split()) <= 3 and 
            line.istitle() and 
            not any(word in line.lower() for word in ['resume', 'cv', 'vitae'])):
            return line
    
    # Method 2: Look for "Name:" pattern
    if match := re.search(r'(?i)(?:name|full name)[:\s]*(.*?)\n', text):
        return match.group(1).strip()
    
    # Method 3: First non-empty line
    for line in text.split('\n'):
        if line.strip():
            return line.strip()
    
    return "Unknown Candidate"

def extract_email_from_resume(text: str) -> Optional[str]:
    """Extract email address using regex"""
    if match := re.search(r'[\w\.-]+@[\w\.-]+(?:\.[\w]+)+', text):
        return match.group(0)
    return None

def extract_phone(text: str) -> Optional[str]:
    """Extract phone number with international support"""
    patterns = [
        r'(?:(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',  # US/CA
        r'(?:(?:\+?\d{4}[-.\s]?){2,4})',  # International
    ]
    for pattern in patterns:
        if match := re.search(pattern, text):
            return match.group(0)
    return None

def calculate_total_experience(text: str) -> float:
    """Calculate total experience in years from work history"""
    experience_patterns = [
        r'(?:experience|work history|employment)[\s\S]*?(\d+)\s*(?:years?|yrs?)',
        r'(\d+)\s*\+\s*years?\s*experience',
        r'total experience.*?(\d+)'
    ]
    
    # First try explicit experience mentions
    for pattern in experience_patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue
    
    # Fallback: Parse work history dates
    date_ranges = re.findall(
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4}.*?'
        r'(?:to|–|-|present|now|current|\d{4})', 
        text, 
        re.IGNORECASE
    )
    
    total_days = 0
    for date_range in date_ranges[:3]:  # Check first 3 positions
        dates = re.findall(
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4}',
            date_range, 
            re.IGNORECASE
        )
        if len(dates) >= 2:
            start = dateparser.parse(dates[0])
            end = dateparser.parse(dates[1]) if not re.search(r'(present|now|current)', date_range, re.I) else datetime.now()
            if start and end:
                total_days += (end - start).days
    
    return round(total_days / 365, 1)  # Convert to years

def extract_skills_section(text: str) -> List[str]:
    """Extract skills from dedicated skills section"""
    if match := re.search(
        r'(?:technical )?skills(?:\:)?\s*([\s\S]*?)(?:\n\n|\Z|experience|work history)',
        text, 
        re.IGNORECASE
    ):
        skills_text = match.group(1)
        return list(set(
            skill.strip() 
            for skill in re.split(r'[,•·\-—]', skills_text) 
            if skill.strip()
        ))
    return []

def extract_education(text: str) -> List[str]:
    """Extract education degrees"""
    degrees = [
        'phd', 'mba', 'master', 'bachelor', 'bs', 'ms', 
        'ph\.d', 'b\.tech', 'm\.tech', 'bsc', 'msc'
    ]
    found = []
    for line in text.split('\n'):
        if any(re.search(rf'\b{degree}\b', line.lower()) for degree in degrees):
            found.append(line.strip())
    return found[:3]  # Return max 3 most relevant

def process_resume_match(position: str, 
                       searched_skills: List[str], 
                       min_experience: int, 
                       priority: str = 'medium') -> List[Dict[str, Any]]:
    
    """
    Process all resumes and return matches sorted by score
    
    Args:
        position: Job position name
        searched_skills: List of required skills
        min_experience: Minimum years required
        priority: 'high'/'medium'/'low' (affects scoring)
    
    Returns:
        List of candidate dicts sorted by match score
    """
    results = []
    resumes_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
    
    if not os.path.exists(resumes_dir):
        logger.warning(f"Resumes directory not found: {resumes_dir}")
        return results
    
    for filename in os.listdir(resumes_dir):
        if not filename.lower().endswith(('.pdf', '.docx')):
            continue
            
        try:
            filepath = os.path.join(resumes_dir, filename)
            text = extract_text_from_resume(filepath)
            
            if not text:
                logger.debug(f"Empty text in file: {filename}")
                continue
                
            # Extract candidate info using the best available method
            candidate_info = extract_candidate_info(text)
            
            print(f"\n--- Debug Info for {filename} ---")
            print(f"Name: {candidate_info.get('name', 'Not found')}")
            print(f"Email: {candidate_info.get('email', 'Not found')}")
            print(f"Experience: {candidate_info.get('experience', 0)} years")
            print(f"Skills detected: {candidate_info.get('skills', [])}")
            print(f"Text sample: {text[:200]}...\n")
            
            logger.debug("Processing resume: %s", filename)
            logger.debug("Candidate: %s", candidate_info.get('name'))
            logger.debug("Experience: %s years", candidate_info.get('experience'))
            logger.debug("Skills found: %s", candidate_info.get('skills', []))
            
            candidate_skills = extract_skills_from_resume(text, searched_skills)
            
            # Calculate detailed match score
            score, matched_skills, missing_skills = calculate_match_score(
                resume_skills=candidate_skills,
                job_skills=searched_skills,
                min_experience=min_experience,
                resume_experience=candidate_info.get('experience', 0)
            )
            
            # Apply priority adjustment
            if priority == 'high':
                score = min(100, score * 1.1)
            elif priority == 'low':
                score = score * 0.9
                
            if score > 0:  # Only include qualifying candidates
                logger.info("Good match found: %s (Score: %s)", filename, score)
                results.append({
                    'name': candidate_info.get('name', filename),
                    'score': round(score, 1),
                    'matched_skills': matched_skills,
                    'missing_skills': missing_skills,
                    'experience': candidate_info.get('experience', 0),
                    'filename': filename,
                    'resume_url': f'/resumes/{filename}'
                })
                
        except Exception as e:
            logger.error(f"Error processing {filename}: {str(e)}", exc_info=True)
            print(f"Error processing {filename}: {str(e)}")
            continue
    
    logger.info(f"Processing complete. Found {len(results)} matches")
    return sorted(results, key=lambda x: x['score'], reverse=True)

def process_resume(filepath: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
    """Complete resume processing pipeline"""
    text = extract_text_from_resume(filepath)
    if not text:
        return None
        
    skills = extract_skills_from_resume(text, requirements.get('skills', []))
    experience = extract_experience(text)
    
    return {
        'name': text.split('\n')[0].strip() or os.path.basename(filepath),
        'skills': skills,
        'experience': experience,
        'score': calculate_match_score(
            skills,
            requirements['skills'],
            requirements.get('min_experience', 0),
            experience
        ),
        'source': 'Gemini' if GEMINI_API_KEY and len(skills) > 0 else 'Direct'
    }
    
# hrapp/utils.py
from django.core.exceptions import ImproperlyConfigured

def get_email_config(request=None):
    """
    Dynamic email configuration loader with validation
    Returns validated email settings or raises ImproperlyConfigured
    """
    def validate_config(config):
        required_fields = ['email_backend', 'email_host', 'email_port', 
                          'email_username', 'email_password']
        if not all(config.get(field) for field in required_fields):
            raise ImproperlyConfigured("Email configuration incomplete")
        
        try:
            return {
                'EMAIL_BACKEND': config['email_backend'],
                'EMAIL_HOST': config['email_host'],
                'EMAIL_PORT': int(config['email_port']),
                'EMAIL_USE_TLS': bool(config.get('use_tls', True)),
                'EMAIL_HOST_USER': config['email_username'],
                'EMAIL_HOST_PASSWORD': config['email_password']
            }
        except (ValueError, KeyError) as e:
            raise ImproperlyConfigured(f"Invalid email configuration: {str(e)}")

    # 1. Check session first
    if request and 'email_config' in request.session:
        return validate_config(request.session['email_config'])
    
    # 2. Check database configuration
    try:
        from .models import EmailConfiguration
        if request and request.user.is_authenticated:
            config = EmailConfiguration.objects.get(user=request.user)
            return validate_config({
                'email_backend': config.email_backend,
                'email_host': config.email_host,
                'email_port': config.email_port,
                'use_tls': config.use_tls,
                'email_username': config.email_username,
                'email_password': config.email_password
            })
    except Exception:
        pass
    
    # 3. Fallback to settings.py (if any defaults exist)
    from django.conf import settings
    if hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST:
        return {
            k: getattr(settings, k) 
            for k in ['EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT',
                     'EMAIL_USE_TLS', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']
            if hasattr(settings, k)
        }
    
    raise ImproperlyConfigured("Email configuration not found in session, database, or settings")
def test_email_connection(backend: str, host: str, port: int, 
                         username: str, password: str, use_tls: bool) -> Tuple[bool, str]:
    """Test email server connection with detailed error reporting
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        if 'imap' in backend.lower():
            with IMAP4_SSL(host, port, timeout=10) as imap:
                imap.login(username, password)
                imap.logout()
                return True, "IMAP connection successful"
                
        else:  # SMTP
            if use_tls:
                with SMTP_SSL(host, port, timeout=10) as smtp:
                    smtp.login(username, password)
                    return True, "SMTP (SSL) connection successful"
            else:
                with SMTP(host, port, timeout=10) as smtp:
                    smtp.starttls()
                    smtp.login(username, password)
                    return True, "SMTP (STARTTLS) connection successful"
                    
    except socket_timeout:
        return False, "Connection timed out"
    except SSLError as e:
        return False, f"SSL error: {str(e)}"
    except IMAP4.error as e:
        return False, f"IMAP error: {str(e)}"
    except SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"