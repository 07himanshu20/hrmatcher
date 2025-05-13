from django.core.management.commands.runserver import Command as RunserverCommand
from hrapp.tasks import fetch_resumes_from_email
from threading import Thread

class Command(RunserverCommand):
    def handle(self, *args, **options):
        # Start resume fetcher in background thread
        Thread(target=fetch_resumes_from_email, daemon=True).start()
        super().handle(*args, **options)