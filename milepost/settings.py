"""Settings for the Milepost public site.

WHAT THIS PROJECT IS, AND WHAT IT IS NOT YET
---------------------------------------------
This is the second repository the design document has been pointing at: the
public site, and eventually the marketplace service behind it. Today it is
the marketing half only -- pages that say what Milepost is -- because that
half depends on nothing unbuilt, and because a family cannot be sold a
subscription before there is anywhere to send them.

`docs/marketplace-design.md` in the homeschool-lms repository settles the
shape this grows into: one Django project, one Postgres database, four apps
(`accounts`, `billing`, `catalog`, `instances`), and marketing pages as
templates in the same project. Those apps are deliberately NOT scaffolded
here. An empty app with no models is a claim that work has started when it
has not; each one arrives with its first model.

READING CONFIGURATION: EMPTY MEANS ABSENT
------------------------------------------
`env()` below treats a present-but-empty environment variable as missing.
That is a direct inheritance from a bug in homeschool-lms, and it is worth
the paragraph.

That project's `.env.example` listed `SERVER_EMAIL=` and `LOG_DIR=` with no
values. Deployments copied the example, so the variables were *present and
empty* -- and `os.environ.get('SERVER_EMAIL', default)` returns `''` for a
present key, never the default. Every such deployment sent error mail from
nobody and wrote its logs to whatever directory the process happened to start
in, silently, because an empty string is falsy in exactly the places nobody
looks. The test that eventually caught it had been passing by comparing two
empty values.

So: empty is absent, here, from the first commit, before there is a
deployment to get it wrong.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Local configuration from .env, if there is one. Real environment variables
# take precedence, so a properly configured server needs no .env file at all
# -- the same arrangement, and the same call, as homeschool-lms uses, because
# an operator should not have to hold two ideas about how these are set up.
load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    """An environment variable, where blank counts as unset.

    See the module docstring. `os.environ.get`'s own fallback is the thing
    this exists to avoid depending on.
    """
    value = os.environ.get(name, '')
    return value.strip() if value.strip() else default


def env_bool(name, default=False):
    value = env(name)
    if value is None:
        return default
    return value.lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=()):
    value = env(name)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(',') if item.strip()]


DEBUG = env_bool('DJANGO_DEBUG', default=False)

# A throwaway key in development only. In production the absence of a real one
# is a startup failure rather than a silently insecure default -- the failure
# mode this whole module is written to avoid.
SECRET_KEY = env('DJANGO_SECRET_KEY')
if SECRET_KEY is None:
    if DEBUG:
        SECRET_KEY = 'dev-only-key-not-used-to-sign-anything-real'
    else:
        raise RuntimeError(
            'DJANGO_SECRET_KEY is unset or empty and DJANGO_DEBUG is False. '
            'Set a real key; see .env.example.'
        )

ALLOWED_HOSTS = env_list(
    'DJANGO_ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1'] if DEBUG else [],
)

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    # That is the whole list, and it is short on purpose.
    #
    # No auth, sessions, admin, messages or contenttypes. They arrive with
    # `accounts`, which is the app that first needs a user. Marketing pages
    # have no models, so today this project needs no database at all -- and
    # including contenttypes anyway means two unapplied migrations nagging on
    # every runserver about a database nothing reads. A site that ships
    # session middleware it does not use is also a cookie it does not need to
    # set, which matters more than usual on a page aimed at families who are
    # deliberate about what they hand over.
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'milepost.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
    ]},
}]

WSGI_APPLICATION = 'milepost.wsgi.application'

# Nothing reads this yet -- see INSTALLED_APPS. It is configured now because
# the switch itself is the convention worth fixing early: SQLite until DB_HOST
# is set, which is the entire switch to Postgres, exactly as homeschool-lms
# does it, so an operator does not have to hold two ideas about how these
# projects are configured.
if env('DB_HOST'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', 'milepost'),
        'USER': env('DB_USER', 'milepost'),
        'PASSWORD': env('DB_PASSWORD', ''),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', '5432'),
    }}
else:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOG_DIR = Path(env('LOG_DIR', BASE_DIR / 'logs'))

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
