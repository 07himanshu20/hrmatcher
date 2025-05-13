from django.db import models
from django.contrib.auth.models import User

# models.py
class JobRequirement(models.Model):
    position = models.CharField(max_length=255, default='Default Position')  # Must include default
    skills = models.TextField()
    min_experience = models.IntegerField()
    min_score = models.FloatField(default=0.0)

    def get_skills_list(self):
        return [skill.strip().lower() for skill in self.skills.split(',')]

class Candidate(models.Model):
    name = models.CharField(max_length=255, blank=True, default="Unknown Candidate")
    resume = models.FileField(upload_to='resumes/')
    score = models.IntegerField()
    matched = models.BooleanField()

class EmailConfiguration(models.Model):
    user = models.OneToOneField(  # Changed from ForeignKey
        User,
        on_delete=models.CASCADE,
        related_name='email_config',  # Singular since OneToOne
        db_index=True  # Add database index
    )
    email_host = models.CharField(max_length=255)
    email_port = models.IntegerField()
    email_username = models.CharField(max_length=255)
    email_password = models.CharField(max_length=255)
    use_tls = models.BooleanField(default=True)
    
    
    
    email_backend = models.CharField(max_length=255, default='django.core.mail.backends.smtp.EmailBackend')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
         return f"Email config for {self.user.username}"  # Changed from self.name
     
