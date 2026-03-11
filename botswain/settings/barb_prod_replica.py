"""
Settings for connecting to BARB production read-replica.
Safe read-only access to production data.
"""
from .base import *

DEBUG = True  # Keep debug on for local development
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Multi-database setup:
# - 'default': Botswain's own database (for QueryLog, audit data, etc.)
# - 'barb': BARB production read-replica (READ-ONLY, for instrument queries)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # Local SQLite database for Botswain data
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
    }
}

# Database router: BARB models go to 'barb', Botswain models go to 'default'
DATABASE_ROUTERS = ['botswain.db_router.BarbDatabaseRouter']

# Use BARB's app labels for models
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
    'data_sources',  # Unmanaged BARB models
]
