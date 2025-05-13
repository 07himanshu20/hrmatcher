from django.contrib import admin, messages
from .tasks import fetch_resumes_from_email

@admin.action(description='Fetch resumes from email')
def admin_fetch_resumes(modeladmin, request, queryset):
    try:
        fetch_resumes_from_email()  # Synchronous call
        messages.success(request, "Resumes fetched successfully!")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")

class YourModelAdmin(admin.ModelAdmin):
    actions = [admin_fetch_resumes]