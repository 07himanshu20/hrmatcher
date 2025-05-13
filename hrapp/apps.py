# hrapp/apps.py
from django.apps import AppConfig

class HrappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hrapp'

    def ready(self):
        # Import signals after apps are loaded
        if not hasattr(self, '_signals_loaded'):
            from . import signals  # noqa
            self._signals_loaded = True