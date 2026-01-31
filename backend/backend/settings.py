"""
Django settings for backend project.
生产环境优化版本 (Production-Ready Version)
"""

from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量，这对于本地开发测试生产配置非常有用
# 在 Docker 环境中，我们通常会直接通过 docker-compose 注入环境变量
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
CORS_ALLOW_ALL_ORIGINS = True
# ==============================================================================
# 核心安全配置 (CORE SECURITY SETTINGS)
# ==============================================================================

# 绝不硬编码！必须从环境变量中读取
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("No DJANGO_SECRET_KEY set for Django project")

# 生产环境中必须为 False！
# 为了方便，我们可以让它根据环境变量来决定，这样在开发时可以设为 True
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 't')

# 生产环境中必须配置允许访问的域名
# 从环境变量读取，并用逗号分隔
# 示例环境变量：ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your_server_ip
ALLOWED_HOSTS_str = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
#ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_str.split(',')]
ALLOWED_HOSTS=['*']

# ==============================================================================
# 应用注册 (APPLICATION DEFINITION)
# ==============================================================================

INSTALLED_APPS = [
    # Django 默认模块
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # 第三方模块
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'allauth.socialaccount.providers.microsoft',
    'dj_rest_auth',
    'dj_rest_auth.registration',

    # 自定义应用
    'chatbot',
    'extension',
    'accounts',
]

AUTH_USER_MODEL = 'accounts.User'
SITE_ID = 2  # allauth 需要

# ==============================================================================
# 中间件 (MIDDLEWARE)
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 新增：Whitenoise 用于在生产环境服务静态文件，如果用 Nginx 则不需要
    # 'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware', # 建议放在 SecurityMiddleware 之后，其他常用中间件之前
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.sites.middleware.CurrentSiteMiddleware', # allauth 0.50+ 已弃用
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]


# ==============================================================================
# URL 配置
# ==============================================================================

ROOT_URLCONF = 'backend.urls'
WSGI_APPLICATION = 'backend.wsgi.application'


# ==============================================================================
# 数据库 (DATABASES)
# ==============================================================================

# 生产环境强烈建议使用 PostgreSQL 或 MySQL，而不是 SQLite
# 下面的配置使其可以根据环境变量动态选择
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'), # 在 Docker Compose 中，这通常是数据库服务的名字，如 'db'
            'PORT': os.getenv('DB_PORT'),
        }
    }


# ==============================================================================
# 密码验证 (PASSWORD VALIDATION)
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ==============================================================================
# 国际化 (INTERNATIONALIZATION)
# ==============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ==============================================================================
# 静态文件与媒体文件 (STATIC & MEDIA FILES)
# ==============================================================================

STATIC_URL = '/static/'
# 生产环境中运行 `collectstatic` 命令时，静态文件会被收集到这个目录
STATICFILES_DIRS = [
    BASE_DIR / 'backend' / 'static',  # 你放 favicon.ico 的目录
]

# 生产环境 collectstatic 目录
STATIC_ROOT = BASE_DIR / 'staticfiles'

# 媒体文件
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'


# ==============================================================================
# 模板 (TEMPLATES)
# ==============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ==============================================================================
# CORS (Cross-Origin Resource Sharing)
# ==============================================================================

# 生产环境中，CORS_ALLOWED_ORIGINS 应该只包含你的前端域名
# 从环境变量读取，用逗号分隔
# 示例：CORS_ALLOWED_ORIGINS=https://your-frontend.com,http://localhost:5173
CORS_ALLOWED_ORIGINS_str = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS_str.split(',')]

CORS_ALLOW_CREDENTIALS = True
# 以下配置通常保持不变
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type', 'dnt', 'origin',
    'user-agent', 'x-csrftoken', 'x-requested-with',
]


# ==============================================================================
# REST FRAMEWORK & AUTHENTICATION
# ==============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

REST_AUTH = {
    'USE_JWT': True,
    'TOKEN_MODEL': None,
    'JWT_AUTH_HTTPONLY': False,
    'REGISTER_SERIALIZER': 'accounts.serializers.RegisterSerializer',
    # 在生产中，如果你的前端和后端在同一个主域名下，可以考虑使用 HttpOnly Cookie
    # 'JWT_AUTH_COOKIE': 'my-app-auth',
    # 'JWT_AUTH_REFRESH_COOKIE': 'my-refresh-token',
    # 'JWT_AUTH_SECURE': not DEBUG, # 在 HTTPS 下使用 Secure Cookie
}


# ==============================================================================
# AllAuth 配置
# ==============================================================================

ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'none' # 或者 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
# ACCOUNT_ADAPTER = 'accounts.adapter.MyAccountAdapter' # 如果有自定义 adapter
# SOCIALACCOUNT_ADAPTER = 'accounts.adapter.MySocialAccountAdapter' # 如果有自定义 social adapter

# 社交登录凭证，从环境变量读取
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET'),
        },
    },
    'github': {
        'SCOPE': ['user:email'],
        'APP': {
            'client_id': os.getenv('GITHUB_CLIENT_ID'),
            'secret': os.getenv('GITHUB_CLIENT_SECRET'),
        },
    },
    'microsoft': {
        'SCOPE': ['User.Read', 'email'],
        'APP': {
            'client_id': os.getenv('MICROSOFT_CLIENT_ID'),
            'secret': os.getenv('MICROSOFT_CLIENT_SECRET'),
        },
    },
}
SOCIALACCOUNT_AUTO_SIGNUP = True

# ==============================================================================
# 日志 (LOGGING)
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        # 将日志输出到控制台，这在 Docker 环境中是最佳实践
        # Docker 会收集容器的标准输出作为日志
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'DEBUG'),
            'propagate': False,
        },
    },
}

# ==============================================================================
# 默认主键 (DEFAULT PRIMARY KEY)
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'