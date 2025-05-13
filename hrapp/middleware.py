# hrapp/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import EmailConfiguration
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware(MiddlewareMixin):
    exempt_paths = [
        reverse('login'),
        reverse('logout'),
        reverse('email_config'),
        reverse('resume_matcher'),
        '/admin/',
        '/static/',
        '/media/',
        '/favicon.ico'
    ]

    def process_request(self, request):
        if any(request.path.startswith(p) for p in self.exempt_paths):
            return

        if not request.user.is_authenticated:
            messages.info(request, 'Please login to continue')
            return redirect(f"{reverse('login')}?next={request.path}")

        try:
            if not request.session.get('email_configured'):
                if not EmailConfiguration.objects.filter(user=request.user).exists():
                    messages.warning(request, 'Email configuration required')
                    return redirect('email_config')
                
                request.session['email_configured'] = True
                request.session.modified = True

        except Exception as e:
            logger.error(f"Configuration check failed: {str(e)}")
            messages.error(request, 'System configuration error')
            return redirect('login')

        return