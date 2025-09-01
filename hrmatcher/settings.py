
from pathlib import Path
from celery.schedules import crontab  # Explicit import for crontab
# At the top with other imports
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent
# At the bottom of settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {module} {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'rotating_file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'resume_matcher.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose'
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'rotating_file'],
            'level': 'DEBUG',
        },
        'your_app.utils': {  # Specific logger for your utils
            'handlers': ['rotating_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure--4g%)wduh)z@5#g2o4v25b((!*t7j7*qg%dsvm_ah0dtu(y5fx'


DEBUG = False

ALLOWED_HOSTS = ['bharatcrest.com', 'www.bharatcrest.com', '127.0.0.1', 'localhost']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
    'django_celery_results',
    'hrapp.apps.HrappConfig',
    
]

# settings.py (Corrected)

# Use URL pattern NAMES not paths
LOGIN_URL = 'login'  # Name of your login URL pattern
LOGIN_REDIRECT_URL = 'email_config'  # Name of email config URL pattern
LOGOUT_REDIRECT_URL = 'login'  # Name of login URL pattern

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'hrapp.middleware.SecurityMiddleware',
]



LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

import os
ROOT_URLCONF = 'hrmatcher.urls'

import environ

# Initialize the environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(str(BASE_DIR), '.env'))

def get_email_config(request=None):
    """Dynamic email configuration loader"""
    default_config = {
        'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'EMAIL_HOST': '',
        'EMAIL_PORT': 993,
        'EMAIL_USE_TLS': True,
        'EMAIL_HOST_USER': '',
        'EMAIL_HOST_PASSWORD': '',
    }
    
    if request and 'email_config' in request.session:
        config = request.session['email_config']
        return {
            'EMAIL_BACKEND': config['email_backend'],
            'EMAIL_HOST': config['email_host'],
            'EMAIL_PORT': config['email_port'],
            'EMAIL_USE_TLS': config['use_tls'],
            'EMAIL_HOST_USER': config['email_username'],
            'EMAIL_HOST_PASSWORD': config['email_password'],
        }
    
    return default_config


'''
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'imap.secureserver.net'
EMAIL_PORT = 993
'''
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_USER')  # Loaded from .env
EMAIL_HOST_PASSWORD = env('EMAIL_PASSWORD')  # Loaded from .env

# Path to save resumes
RESUME_FILE_PATH = env('RESUME_FILE_PATH')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        
        'DIRS': [
                    BASE_DIR / 'hrmatcher/templates',
                    BASE_DIR / 'templates',
                    
                ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hrmatcher.wsgi.application'

# settings.py
CELERY_BEAT_SCHEDULE = {
    'process-resumes-hourly': {
        'task': 'hrapp.tasks.process_resumes_from_email',
        'schedule': crontab(hour='*/1'),
        'args': (0,),  # Will be updated in the task itself
    }
}

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Logging configuration (add to the bottom)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/resume_matcher.log'),
        },
    },
    'loggers': {
        '': {  # Root logger
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


# Celery Settings

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TIMEZONE = 'UTC'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True 
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Optional: Celery Results Database
CELERY_RESULT_BACKEND = 'django-db'

# Add this to your settings.py
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Or any preferred directory name

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Your app-specific static files
]

# Adding Celery Result Model for tasks to be tracked
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose'
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'your_app': {  # Replace 'your_app' with your actual app name
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
