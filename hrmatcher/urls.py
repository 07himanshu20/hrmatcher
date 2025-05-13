import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve  # Add this import
from django.contrib.auth import views as auth_views  # Add this import
from hrapp.views import email_config_view, resume_matcher_view  # Your views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('hrapp.urls')),
    
] 
urlpatterns += [
    path('media/resumes/<path:path>', serve, {
        'document_root': os.path.join(settings.MEDIA_ROOT, 'resumes'),
    }),
]
