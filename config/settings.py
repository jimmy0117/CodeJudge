from pathlib import Path
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

# 正式環境安全防呆：DEBUG=False 卻還在用預設的 SECRET_KEY，代表 .env 沒有正確設定，
# 寧可啟動失敗也不要讓平台帶著不安全的預設值上線。詳見 README「正式部署前檢查清單」。
if not DEBUG and SECRET_KEY == 'django-insecure-change-me-in-production':
    raise ImproperlyConfigured(
        'DJANGO_DEBUG=False 但 DJANGO_SECRET_KEY 還是預設值，'
        '請在 .env 設定一組隨機的 DJANGO_SECRET_KEY 後再啟動。'
    )

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'crispy_forms',
    'crispy_bootstrap5',
    'social_django',
    # Local apps
    'accounts',
    'questions',
    'practice',
    'exams',
    'classes',
    'dashboard',
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

ROOT_URLCONF = 'config.urls'

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
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
                'accounts.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='apcs_db'),
        'USER': config('POSTGRES_USER', default='apcs_user'),
        'PASSWORD': config('POSTGRES_PASSWORD', default='apcs_password'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hant'
TIME_ZONE = 'Asia/Taipei'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ── Google OAuth 2.0 ──────────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]

SOCIAL_AUTH_URL_NAMESPACE = 'social'

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY    = config('GOOGLE_OAUTH2_CLIENT_ID', default='')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = config('GOOGLE_OAUTH2_CLIENT_SECRET', default='')

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'accounts.pipeline.ensure_user_profile',   # 確保 UserProfile 存在
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)

SOCIAL_AUTH_STRATEGY             = 'accounts.social_strategy.DBDjangoStrategy'
SOCIAL_AUTH_LOGIN_REDIRECT_URL   = '/'
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/'
SOCIAL_AUTH_REDIRECT_IS_HTTPS    = False   # 開發環境使用 HTTP

# ── Email（忘記密碼等系統信件）────────────────────────────────────────────────
# 預設用 console backend：信件內容印到 web 容器 log，開發環境不需要架設 SMTP。
# 正式環境要真的寄出信件，在 .env 設定 EMAIL_BACKEND 為
# django.core.mail.backends.smtp.EmailBackend，並填好下方 SMTP 相關變數。
EMAIL_BACKEND = config(
    'EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL', default='APCS 練習平台 <noreply@apcs-practice.local>'
)
PASSWORD_RESET_TIMEOUT = config('PASSWORD_RESET_TIMEOUT', default=3600, cast=int)  # 秒，預設 1 小時

# ── HTTPS 安全性設定（正式部署用）───────────────────────────────────────────────
# 目前 docker-compose 用 `runserver` 直接對外，8443 只是 port 號碼，並不是真的 TLS。
# 正式上線時要在前面加一層會做 TLS termination 的反向代理（Nginx / Caddy 等，
# 見 README「未來擴充方向」），確認 HTTPS 真的生效後，再把 DJANGO_USE_HTTPS 設為
# True——這裡才會強制 HTTPS 轉址、cookie 加上 Secure 旗標。沒有 TLS 的情況下打開
# 這個開關，網站會直接進入無窮轉址迴圈，因此預設關閉。
USE_HTTPS = config('DJANGO_USE_HTTPS', default=False, cast=bool)
if USE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
