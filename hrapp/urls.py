from django.urls import path
from . import views
from django.contrib import admin
from django.contrib.auth import views as auth_views
from .views import custom_login
from django.contrib.auth.views import LoginView


urlpatterns = [
  
   
   path('login/', views.custom_login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('email-config/', views.email_config_view, name='email_config'),
    
   
    path('resume_matcher/', views.resume_matcher_view, name='resume_matcher'),
    path('match-resumes/', views.match_resumes, name='match_resumes'), 
    path('resume/<str:filename>/', views.view_resume, name='view_resume'),
    path('export/<str:format_type>/', views.export_results, name='export_results'),  
    path('test-email-connection/', views.test_email_connection, name='test_email_connection'),  
    
    path('', views.root_redirect, name='root_redirect'),

]