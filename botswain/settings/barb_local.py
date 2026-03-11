"""
Settings for connecting to local BARB database.
Use this to test Botswain with real BARB data.
"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Connect to BARB's PostgreSQL database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'barb_local',
        'USER': 'barb',
        'PASSWORD': '',  # BARB uses trust auth locally
        'HOST': 'localhost',
        'PORT': '5434',  # BARB runs on port 5434
    }
}

# Tell Django to use BARB's existing tables (don't run migrations)
DATABASE_ROUTERS = []

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
]
