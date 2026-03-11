import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'core',
    'api',
    'data_sources.barb',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'botswain.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'botswain.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'botswain'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# LLM Provider Configuration
LLM_PROVIDER = os.environ.get('BOTSWAIN_LLM_PROVIDER', 'bedrock')

# AWS Bedrock Configuration
BEDROCK_MODEL_ID = os.environ.get(
    'BEDROCK_MODEL_ID',
    'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
)
BEDROCK_MAX_INTENT_TOKENS = int(os.environ.get('BEDROCK_MAX_INTENT_TOKENS', '500'))
BEDROCK_MAX_RESPONSE_TOKENS = int(os.environ.get('BEDROCK_MAX_RESPONSE_TOKENS', '1000'))
BEDROCK_AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
BEDROCK_TIMEOUT = float(os.environ.get('BEDROCK_TIMEOUT', '30.0'))

# Redis Cache Configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': 'botswain',
        'TIMEOUT': 300,  # Default 5 minutes
    }
}

# Per-Entity Cache TTL Configuration (in seconds)
ENTITY_CACHE_TTL = {
    # Real-time data - short TTL
    'synthesizer': 30,        # Synthesizer status changes frequently
    'instrument': 30,         # Instrument status changes frequently
    'workflow': 60,           # Workflow execution status
    'ecs_service': 60,        # ECS service deployment status

    # Semi-static data - medium TTL
    'order': 300,             # Orders don't change often once placed (5 min)
    'netsuite_order': 600,    # NetSuite sync data (10 min)
    'github_issue': 300,      # GitHub issues (5 min)
    'rds_database': 300,      # RDS metrics update periodically (5 min)

    # Static/historical data - long TTL
    'git_commit': 3600,       # Git history doesn't change (1 hour)

    # Disabled entities (for future use)
    'kraken_workflow': 60,    # When enabled: workflow status
    'sos_sequencing': 300,    # When enabled: sequencing orders (5 min)
}

# Cache bypass for fresh data
CACHE_BYPASS_HEADER = 'X-Botswain-Cache-Bypass'  # Set to '1' to bypass cache
