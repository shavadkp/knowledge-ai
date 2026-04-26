import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-change-this-in-production-xyz123'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'knowledge_api',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'backend.urls'
WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

CORS_ALLOW_ALL_ORIGINS = True

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL = '/static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Max upload size: 20MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# Chunk settings for RAG
CHUNK_SIZE = 500          # characters per chunk
CHUNK_OVERLAP = 50        # overlap between chunks
TOP_K_RESULTS = 3         # number of chunks to retrieve

# Anthropic API Key - set via environment variable
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
