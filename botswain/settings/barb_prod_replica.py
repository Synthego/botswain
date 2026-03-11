"""
Settings for connecting to BARB production read-replica.
Safe read-only access to production data.
"""
import os
from .base import *

DEBUG = True  # Keep debug on for local development
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Multi-database setup:
# - 'default': Botswain's own database (for QueryLog, audit data, etc.)
# - 'barb': BARB production read-replica (READ-ONLY, for instrument queries)
# - 'buckaneer': Buckaneer production primary (READ-ONLY, for NetSuite order queries)
# - 'kraken': Kraken production primary (READ-ONLY, for workflow orchestration queries)
# - 'sos': SOS production primary (READ-ONLY, for sequencing order queries)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # Local SQLite database for Botswain data
    },
    'barb': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'barb',
        'USER': 'readonlyuser',
        'PASSWORD': os.environ.get('BARB_READONLY_PASSWORD', ''),
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
        'PASSWORD': os.environ.get('BUCKANEER_PASSWORD', ''),
        'HOST': 'buckaneer-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
    },
    # DISABLED: Kraken and SOS databases not accessible (not in AWS RDS)
    # These services appear to run on internal .ad.synthego.com infrastructure
    # To re-enable: uncomment these sections and verify network connectivity
    # 'kraken': {
    #     'ENGINE': 'django.db.backends.postgresql',
    #     'NAME': 'kraken',
    #     'USER': 'kraken',
    #     'PASSWORD': os.environ.get('KRAKEN_DB_PASSWORD', ''),
    #     'HOST': 'kraken-prod-pg-0.cb7xtwywa7y5.us-west-2.rds.amazonaws.com',
    #     'PORT': '5432',
    #     'OPTIONS': {
    #         'connect_timeout': 10,
    #     },
    # },
    # 'sos': {
    #     'ENGINE': 'django.db.backends.postgresql',
    #     'NAME': 'sos',
    #     'USER': 'readonlyuser',
    #     'PASSWORD': os.environ.get('SOS_DB_READONLY_PASSWORD', ''),
    #     'HOST': 'sos-prod-pg-01.cb7xtwywa7y5.us-west-2.rds.amazonaws.com',
    #     'PORT': '5432',
    #     'OPTIONS': {
    #         'connect_timeout': 10,
    #     },
    # }
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
