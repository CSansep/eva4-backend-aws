"""
Django settings for backend_project.

Configured according to enterprise DevSecOps standards for AWS EC2,
Amazon RDS (PostgreSQL), and Amazon S3 storage integration.
Compliant with OWASP Top 10, SonarQube SAST, and OWASP ZAP DAST audits.
"""

import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / '.env')

# ------------------------------------------------------------------------------
# 1. CORE SECURITY SETTINGS
# ------------------------------------------------------------------------------
# In production, SECRET_KEY must be stored securely in the environment.
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-eva4-backend-production-dev-key-must-be-replaced-in-env'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# ALLOWED_HOSTS accepts comma-separated values from the environment.
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]

# ------------------------------------------------------------------------------
# 2. APPLICATION DEFINITION
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django core apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    'storages',

    # Local application
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # CORS middleware must be positioned as high as possible, especially before CommonMiddleware
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'backend_project.wsgi.application'
ASGI_APPLICATION = 'backend_project.asgi.application'

# ------------------------------------------------------------------------------
# 3. DATABASE CONFIGURATION (Hybrid: Amazon RDS PostgreSQL / SQLite Local)
# ------------------------------------------------------------------------------
DB_ENGINE = os.environ.get('DB_ENGINE', '').strip()

if DB_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'eva4_db'),
            'USER': os.environ.get('DB_USER', 'eva4_dbuser'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {
                'sslmode': os.environ.get('DB_SSLMODE', 'prefer'),
            },
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '600')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ------------------------------------------------------------------------------
# 4. CUSTOM USER MODEL & AUTHENTICATION
# ------------------------------------------------------------------------------
AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Cryptographic Password Hashers prioritizing PBKDF2 with SHA-256
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# ------------------------------------------------------------------------------
# 5. INTERNATIONALIZATION & LOCALIZATION
# ------------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------------------
# 6. STATIC AND MEDIA STORAGE (Amazon S3 / Local Fallback)
# ------------------------------------------------------------------------------
USE_S3 = os.environ.get('USE_S3', 'False').lower() in ('true', '1', 't')

if USE_S3:
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
    AWS_SESSION_TOKEN = os.environ.get('AWS_SESSION_TOKEN', None)
    
    # Custom domain or default S3 URL endpoint
    custom_domain = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '')
    if not custom_domain and AWS_STORAGE_BUCKET_NAME:
        AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    else:
        AWS_S3_CUSTOM_DOMAIN = custom_domain

    AWS_S3_OBJECT_PARAMETERS = {
        'ServerSideEncryption': 'AES256',
    }
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True

    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

    STORAGES = {
        "default": {
            "BACKEND": "core.storage_backends.MediaStorage",
        },
        "staticfiles": {
            "BACKEND": "core.storage_backends.StaticStorage",
        },
    }
    # Backward compatibility with Django < 4.2 / legacy storages lookups
    DEFAULT_FILE_STORAGE = "core.storage_backends.MediaStorage"
    STATICFILES_STORAGE = "core.storage_backends.StaticStorage"
else:
    STATIC_URL = '/static/'
    STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
    MEDIA_URL = '/media/'
    MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media')))

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------------------------
# 7. DJANGO REST FRAMEWORK CONFIGURATION
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%SZ',
}

# ------------------------------------------------------------------------------
# 8. SIMPLE JWT CONFIGURATION
# ------------------------------------------------------------------------------
access_lifetime = int(os.environ.get('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', '60'))
refresh_lifetime = int(os.environ.get('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '1'))

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=access_lifetime),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=refresh_lifetime),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# ------------------------------------------------------------------------------
# 9. CORS CONFIGURATION (Frontend EC2 Integration)
# ------------------------------------------------------------------------------
cors_origins_raw = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if cors_origins_raw.strip():
    CORS_ALLOWED_ORIGINS = [orig.strip() for orig in cors_origins_raw.split(',') if orig.strip()]
else:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'True').lower() in ('true', '1', 't')
else:
    CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'False').lower() in ('true', '1', 't')

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ------------------------------------------------------------------------------
# 10. DRF SPECTACULAR (OpenAPI 3.0 / Swagger UI)
# ------------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'EVA4 Task & Project Management API',
    'DESCRIPTION': (
        'Enterprise-grade RESTful API service for multi-tenant workspace, '
        'task management, and secure asset handling on AWS EC2, RDS PostgreSQL, and S3.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]+',
    'ENUM_NAME_OVERRIDES': {
        'UserRoleEnum': 'core.models.RoleChoices',
        'WorkspaceMemberRoleEnum': 'core.models.WorkspaceMemberRoleChoices',
    },
}

# ------------------------------------------------------------------------------
# 11. SECURITY HEADERS (OWASP ZAP DAST & SonarQube SAST Compliance)
# ------------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
REFERRER_POLICY = 'strict-origin-when-cross-origin'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 't')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
    CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
