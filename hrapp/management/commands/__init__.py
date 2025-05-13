from django.core.management.base import BaseCommand
from hrapp.models import JobRequirement

class Command(BaseCommand):
    help = 'Ensures basic JobRequirement exists in database'

    def handle(self, *args, **options):
        if not JobRequirement.objects.exists():
            obj = JobRequirement.objects.create(
                position="Default Position",
                skills="python,django",
                min_experience=1,
                min_score=50.0
            )
            self.stdout.write(self.style.SUCCESS(
                f'Created default JobRequirement (ID: {obj.id})'
            ))
        else:
            self.stdout.write('JobRequirement already exists')