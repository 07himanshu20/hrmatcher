import os
import re
import json
import logging
from typing import List, Dict, Optional
from django.shortcuts import render, redirect, Http404
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from celery.result import AsyncResult
from dotenv import load_dotenv
import google.generativeai as genai
from .forms import JobRequirementForm
from django.contrib.auth.decorators import login_required
from .forms import EmailConfigurationForm
from .models import EmailConfiguration
from django.contrib import messages
from .utils import get_email_config
from .models import Candidate
from .tasks import process_resumes_from_email, fetch_resumes_from_email
from .utils import (
    extract_text_from_resume,
    extract_name_from_resume,
    extract_skills_from_resume,
    extract_experience,
    calculate_match_score,
    get_resume_files,
    test_email_connection,
    extract_email_from_resume,  # Add this
    extract_phone  
)

# Initialize logger
logger = logging.getLogger(__name__)

# Configure Gemini
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

# ====================== Core Views ====================== #
def index(request):
    return render(request, 'hrapp/index.html')

from django.contrib.auth.decorators import login_required
from .models import Candidate

@login_required
def resume_matcher_view(request):
    if not request.session.get('email_config'):
        messages.warning(request, 'Please configure your email settings first')
        return redirect('email_config')
    matched_candidates = []
    
    if request.method == 'POST':
        job_title = request.POST.get('job_title', '')
        skills_input = request.POST.get('skills_to_find', '')
        min_experience = int(request.POST.get('min_experience', 0))
        skills_to_find = [skill.strip() for skill in skills_input.split(',') if skill.strip()]

        resume_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
        
        for filename in os.listdir(resume_dir):
            if filename.lower().endswith(('.pdf', '.docx')):
                resume_path = os.path.join(resume_dir, filename)
                
                try:
                    text = extract_text_from_resume(resume_path)
                    if not text:
                        continue

                    # Try Gemini first, fallback to direct search
                    candidate_data = extract_skills_with_gemini(text, skills_to_find)
                    experience = candidate_data['experience']
                    
                    score = calculate_ats_score(
                        resume_text=text,
                        job_requirements={
                            'required_skills': skills_to_find,
                            'min_experience': min_experience,
                            'job_title_keywords': [job_title.lower()] if job_title else []
                        }
                    )

                    if score['total_score'] > 0 and experience >= min_experience:
                        matched_candidates.append({   'name': candidate_data['name'],
                            'score': score['total_score'],
                            'path': os.path.join(settings.MEDIA_URL, 'resumes', f'user_{request.user.id}', filename).replace('\\', '/'),
                            'matched_skills': score['matched_skills'],
                            'experience': experience
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
                    continue

        matched_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return render(request, 'hrapp/resume_matcher.html', {
        'matched_candidates': matched_candidates
    })

@require_POST
@csrf_exempt 
def match_resumes(request):
    try:
        
        #accessing resumes from the email 
        # First fetch new resumes from email
        from .tasks import fetch_resumes_from_email
        resume_files = fetch_resumes_from_email(request.user.id)
        
        if not resume_files:
            logger.info("No new resumes found in email")
        
        
        skills = [s.strip().lower() for s in request.POST.get('skills', '').split(',') if s.strip()]
        min_experience = int(request.POST.get('min_experience', 0))
        position = request.POST.get('position', '').lower()
        
        resume_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
        results = []

        MAX_RESUMES = 5  # Set your desired limit here

        # List and sort resumes (optional: by newest first)
        all_resumes = [f for f in os.listdir(resume_dir) if f.lower().endswith(('.pdf', '.docx'))]
        all_resumes = sorted(all_resumes, key=lambda x: os.path.getmtime(os.path.join(resume_dir, x)), reverse=True)
        limited_resumes = all_resumes[:MAX_RESUMES]

        for filename in limited_resumes:
            filepath = os.path.join(resume_dir, filename)
            try:
                text = extract_text_from_resume(filepath)
                if not text:
                    continue

                # Use Gemini with fallback
                candidate_data = extract_skills_with_gemini(text, skills)

                ats_score = calculate_ats_score(
                    resume_text=text,
                    job_requirements={
                        'required_skills': skills,
                        'min_experience': min_experience,
                        'job_title_keywords': [position],
                        'preferred_skills': []
                    }
                )
                if ats_score['matched_skills']:
                    results.append({
                        'name': candidate_data['name'],
                        'score': ats_score['total_score'],
                        'matched_skills': ats_score['matched_skills'],
                        'missing_skills': ats_score['missing_skills'],
                        'experience': candidate_data['experience'],
                        'email': candidate_data['email'],
                        'phone': candidate_data['phone'],
                        'filename': filename,
                        'resume_url': os.path.join(settings.MEDIA_URL, 'resumes', filename).replace('\\', '/'),
                    })

            except Exception as e:
                logger.error(f"Error processing {filename}: {str(e)}")
                continue

        results.sort(key=lambda x: x['score'], reverse=True)
        return JsonResponse(results, safe=False)

    except Exception as e:
        logger.error(f"Match resumes error: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

# ====================== Utility Functions ====================== #
def calculate_ats_score(resume_text: str, job_requirements: dict) -> dict:
    """Enhanced ATS scoring with position matching"""
    resume_lower = resume_text.lower()
    scores = {
        'total_score': 0,
        'skill_match': 0,
        'experience_match': 0,
        'title_match': 0,
        'matched_skills': [],
        'missing_skills': []
    }
    
    # Skill Matching (50 points)
    required_skills = [s.lower() for s in job_requirements.get('required_skills', [])]
    matched_skills = [s for s in required_skills if s in resume_lower]
    if required_skills:
        scores['skill_match'] = (len(matched_skills) / len(required_skills)) * 50
        scores['matched_skills'] = matched_skills
        scores['missing_skills'] = list(set(required_skills) - set(matched_skills))
    
    # Experience Matching (30 points)
    min_exp = job_requirements.get('min_experience', 0)
    exp_match = re.search(r'(\d+)\s*(?:years?|yrs?)(?:\s*\+?)?\s*(?:experience|exp)', resume_lower)
    if exp_match:
        resume_exp = float(exp_match.group(1))
        scores['experience_match'] = min(30, (resume_exp / min_exp) * 30) if min_exp > 0 else 0
    
    # Position Matching (20 points)
    position_keywords = [kw.lower() for kw in job_requirements.get('job_title_keywords', [])]
    if position_keywords:
        scores['title_match'] = (sum(kw in resume_lower for kw in position_keywords) / len(position_keywords)) * 20
    
    scores['total_score'] = sum(scores[k] for k in ['skill_match', 'experience_match', 'title_match'])
    return scores

def extract_skills_with_gemini(resume_text: str, searched_skills: List[str]) -> Dict[str, any]:
    """Strict resume parser using Gemini AI with fallback"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"""Extract from resume as JSON:
{{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1234567890",
    "skills": ["only", "requested", "skills"],
    "experience": years
}}
Skills to match: {searched_skills}"""
        response = model.generate_content(prompt)
        data = json.loads(response.text)
        
        return {
            "name": data.get("name", "Unknown").title(),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "skills": [s.lower() for s in data.get("skills", []) if s.lower() in {sk.lower() for sk in searched_skills}],
            "experience": float(data.get("experience", 0)),
            "source": "Gemini"
        }
    except Exception:
        return extract_direct_search_fallback(resume_text, searched_skills)

def extract_direct_search_fallback(resume_text: str, searched_skills: List[str]) -> Dict[str, any]:
    """Fallback skill extractor"""
    text_lower = resume_text.lower()
    return {
        "name": extract_name_from_resume(resume_text),
        "email": extract_email_from_resume(resume_text),
        "phone": extract_phone(resume_text),
        "skills": [s for s in searched_skills if re.search(rf'\b{re.escape(s.lower())}\b', text_lower)],
        "experience": extract_experience(resume_text),
        "source": "DirectSearch"
    }

# ====================== Additional Views ====================== #
def view_resume(request, filename):
    # Normalize filename (handle spaces and special chars)
    clean_name = os.path.basename(filename).replace('%20', ' ')
    filepath = os.path.normpath(os.path.join(settings.MEDIA_ROOT, 'resumes', clean_name))
    
    # Security check - prevent directory traversal
    if not filepath.startswith(os.path.normpath(os.path.join(settings.MEDIA_ROOT, 'resumes'))):
        raise Http404("Invalid file path")
    
    # Debug output
    print(f"Attempting to serve file at: {filepath}")
    print(f"File exists: {os.path.exists(filepath)}")
    
    if not os.path.exists(filepath):
        raise Http404(f"File not found at: {filepath}")
    
    try:
        return FileResponse(open(filepath, 'rb'), content_type='application/pdf')
    except Exception as e:
        print(f"Error opening file: {str(e)}")
        raise Http404("Could not open file")

def upload_requirement(request):
    if request.method == 'POST':
        form = JobRequirementForm(request.POST)
        if form.is_valid():
            job_req = form.save()
            process_resumes_from_email.delay(job_req.id)
            return redirect('dashboard')
    else:
        form = JobRequirementForm()
    return render(request, 'hrapp/upload.html', {'form': form})

def dashboard(request):
    matched_candidates = Candidate.objects.filter(matched=True)
    return render(request, 'hrapp/dashboard.html', {
        'matched_candidates': matched_candidates
    })

def fetch_resumes(request):
    try:
        task = fetch_resumes_from_email.delay()
        return JsonResponse({'status': 'started', 'task_id': task.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
    
    
from .export_utils import export_to_excel, export_to_pdf

from django.views.decorators.csrf import csrf_exempt

from django.http import HttpResponseBadRequest

def export_results(request, format_type):
    if request.method == 'POST':
        try:
            if not request.POST.get('candidates'):
                return HttpResponseBadRequest("Missing candidates data")
            candidates = json.loads(request.POST['candidates'])
            # Convert string lists to actual lists
            for candidate in candidates:
                for field in ['matched_skills', 'missing_skills']:
                    if isinstance(candidate.get(field), str):
                        candidate[field] = [s.strip() for s in candidate[field].split(',') if s.strip()]
                    elif not candidate.get(field):
                        candidate[field] = []

            if format_type == 'excel':
                return export_to_excel(candidates)
            elif format_type == 'pdf':
                return export_to_pdf(candidates)
            else:
                return HttpResponseBadRequest("Invalid format")
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return HttpResponseBadRequest("Invalid request method")

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import EmailConfiguration
from .forms import EmailConfigurationForm

@login_required
def email_config_view(request):
    if request.method == 'POST':
        # For POST requests, create a new form instance with the submitted data
        form = EmailConfigurationForm(request.POST)
        if form.is_valid():
            # Get or create the configuration for this user
            config, created = EmailConfiguration.objects.get_or_create(user=request.user)
            
            # Update the configuration with form data
            config.email_backend = form.cleaned_data['email_backend']
            config.email_host = form.cleaned_data['email_host']
            config.email_port = form.cleaned_data['email_port']
            config.use_tls = form.cleaned_data['use_tls']
            config.email_username = form.cleaned_data['email_username']
            config.email_password = form.cleaned_data['email_password']
            config.save()
            
            # Update session state
            request.session.update({
                'email_config': {
                    'email_backend': config.email_backend,
                    'email_host': config.email_host,
                    'email_port': config.email_port,
                    'use_tls': config.use_tls,
                    'email_username': config.email_username,
                    'email_password': config.email_password
                },
                'email_configured': True
            })
            request.session.modified = True
            
            messages.success(request, 'Email configuration saved successfully!')
            return redirect('resume_matcher')
        else:
            messages.error(request, 'Invalid configuration values')
    else:
        # For GET requests, always create a completely empty form
        form = EmailConfigurationForm()

    # Check if user has existing config (just for the template to know)
    has_existing_config = EmailConfiguration.objects.filter(user=request.user).exists()

    return render(request, 'hrapp/email_config.html', {
        'form': form,
        'existing_config': has_existing_config
    })



from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.http import HttpResponse
from .models import EmailConfiguration



from django.views.decorators.http import require_POST
from django.http import JsonResponse
import imaplib
import smtplib
import logging

logger = logging.getLogger(__name__)

@require_POST
def test_email_connection(request):
    """Test email server connection with user-provided settings"""
    try:
        # Debug: Log all POST data (excluding password)
        safe_post_data = {k: v for k, v in request.POST.items() if k != 'email_password'}
        logger.info(f"Received POST data: {safe_post_data}")
        
        # Get parameters from POST data
        host = request.POST.get('email_host', '').strip()
        port_str = request.POST.get('email_port', '').strip()
        username = request.POST.get('email_username', '').strip()
        password = request.POST.get('email_password', '')
        use_tls = request.POST.get('use_tls') == 'true'
        
        # Log received data (excluding password)
        logger.info(f"Testing connection with: host='{host}', port='{port_str}', username='{username}', use_tls={use_tls}")
        
        # Validate required fields
        if not host:
            return JsonResponse({
                'success': False,
                'message': "Email server address is required"
            }, status=400)
            
        if not port_str:
            return JsonResponse({
                'success': False,
                'message': "Port number is required"
            }, status=400)
            
        if not username:
            return JsonResponse({
                'success': False,
                'message': "Email username is required"
            }, status=400)
            
        if not password:
            return JsonResponse({
                'success': False,
                'message': "Email password is required"
            }, status=400)
        
        # Convert port to integer
        try:
            port = int(port_str)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': f"Invalid port number: {port_str}"
            }, status=400)
        
        # Remove any protocol prefixes from the host
        if host.startswith('http://') or host.startswith('https://'):
            host = host.split('://', 1)[1]
        
        # Determine protocol based on host name
        protocol = 'IMAP' if 'imap' in host.lower() else 'SMTP'

        logger.info(f"Testing {protocol} connection to {host}:{port}")

        # Test connection with better error handling
        try:
            # First test DNS resolution
            import socket
            try:
                socket.gethostbyname(host)
            except socket.gaierror:
                return JsonResponse({
                    'success': False,
                    'message': f"Cannot resolve hostname '{host}'. Please check the server address and your internet connection."
                }, status=400)
                
            # Now test the actual connection
            if protocol == 'IMAP':
                with imaplib.IMAP4_SSL(host, port, timeout=10) as imap:
                    imap.login(username, password)
                    status, _ = imap.select('INBOX')
            else:
                if use_tls:
                    with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
                        smtp.login(username, password)
                else:
                    with smtplib.SMTP(host, port, timeout=10) as smtp:
                        smtp.starttls()
                        smtp.login(username, password)

            logger.info(f"Connection to {host} successful!")
            return JsonResponse({
                'success': True,
                'message': f"{protocol} connection successful!"
            })
            
        except socket.timeout:
            return JsonResponse({
                'success': False,
                'message': f"Connection to {host}:{port} timed out. Please check the server address and port."
            }, status=400)
        except ConnectionRefusedError:
            return JsonResponse({
                'success': False,
                'message': f"Connection to {host}:{port} was refused. Please check the server address and port."
            }, status=400)
        except (imaplib.IMAP4.error, smtplib.SMTPAuthenticationError):
            return JsonResponse({
                'success': False,
                'message': "Authentication failed. Please check your username and password."
            }, status=400)
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f"Connection failed: {str(e)}"
            }, status=400)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f"An unexpected error occurred: {str(e)}"
        }, status=500)
        

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login

def custom_login(request):
    if request.method == 'POST':
        user = authenticate(
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user:
            login(request, user)
            # Force immediate browser-close session
            request.session.set_expiry(0)
            return redirect(reverse('email_config'))
    
    return render(request, 'registration/login.html')

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')
     

def root_redirect(request):
    """Handle root URL redirection"""
    if request.user.is_authenticated:
        return redirect('email_config')  # Changed from 'dashboard' to 'email_config'
    return redirect('login')

from django.contrib.auth import logout
from django.shortcuts import redirect

