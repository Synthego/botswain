"""
Settings for connecting to multiple data sources:
- BARB production read-replica
- Buckaneer production database (READ-ONLY via router)
"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Multi-database setup:
# - 'default': Botswain's own database (for QueryLog, audit data, etc.)
# - 'barb': BARB production read-replica (READ-ONLY)
# - 'buckaneer': Buckaneer production primary (READ-ONLY via router - no replica available)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'barb': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'barb',
        'USER': 'readonlyuser',
        'PASSWORD': 'BARB_READONLY_PASSWORD_HERE',
        'HOST': 'barb-prod-pg-replica-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
    },
    'buckaneer': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'buckaneer_prod',
        'USER': 'buckaneer',
        'PASSWORD': 'BUCKANEER_PASSWORD_HERE',
        'HOST': 'buckaneer-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# Database router for multi-source queries
DATABASE_ROUTERS = ['botswain.multi_db_router.MultiSourceDatabaseRouter']

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
    'data_sources',
]
