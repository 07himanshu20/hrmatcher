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
                        matched_candidates.append({
                            'name': candidate_data['name'],
                            'score': score['total_score'],
                            'path': os.path.join(settings.MEDIA_URL, 'resumes', filename).replace('\\', '/'),  # Force f
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
        
        for filename in os.listdir(resume_dir):
            if filename.lower().endswith(('.pdf', '.docx')):
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
                    if ats_score['matched_skills']:  # This checks if the list is not empty
                        results.append({
                            'name': candidate_data['name'],
                            'score': ats_score['total_score'],
                            'matched_skills': ats_score['matched_skills'],
                            'missing_skills': ats_score['missing_skills'],
                            'experience': candidate_data['experience'],
                            'filename': filename,
                            'resume_url': os.path.join(settings.MEDIA_URL, 'resumes', filename).replace('\\', '/')
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
    "skills": ["only", "requested", "skills"],
    "experience": years
}}
Skills to match: {searched_skills}"""
        response = model.generate_content(prompt)
        data = json.loads(response.text)
        
        return {
            "name": data.get("name", "Unknown").title(),
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

def export_results(request, format_type):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            candidates = data.get('candidates', [])
            
            if format_type == 'excel':
                return export_to_excel(candidates)
            elif format_type == 'pdf':
                return export_to_pdf(candidates)
            else:
                return JsonResponse({'error': 'Invalid format'}, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import EmailConfiguration
from .forms import EmailConfigurationForm

@login_required
def email_config_view(request):
    try:
        instance = EmailConfiguration.objects.get(user=request.user)
    except EmailConfiguration.DoesNotExist:
        instance = None

    if request.method == 'POST':
        form = EmailConfigurationForm(request.POST, instance=instance)
        if form.is_valid():
            config = form.save(commit=False)
            config.user = request.user
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
        form = EmailConfigurationForm(instance=instance)

    return render(request, 'hrapp/email_config.html', {
        'form': form,
        'existing_config': bool(instance)
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
        # Get parameters from POST data
        host = request.POST.get('email_host')
        port = int(request.POST.get('email_port'))
        username = request.POST.get('email_username')
        password = request.POST.get('email_password')
        use_tls = request.POST.get('use_tls') == 'true'
        protocol = 'IMAP' if 'imap' in host.lower() else 'SMTP'

        logger.info(f"Testing {protocol} connection to {host}:{port}")

        # Test connection
        if protocol == 'IMAP':
            with imaplib.IMAP4_SSL(host, port) as imap:
                imap.login(username, password)
                status, _ = imap.select('INBOX')
        else:
            if use_tls:
                with smtplib.SMTP_SSL(host, port) as smtp:
                    smtp.login(username, password)
            else:
                with smtplib.SMTP(host, port) as smtp:
                    smtp.starttls()
                    smtp.login(username, password)

        logger.info(f"Connection to {host} successful!")
        return JsonResponse({
            'success': True,
            'message': f"{protocol} connection successful!"
        })

    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f"Connection failed: {str(e)}"
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

