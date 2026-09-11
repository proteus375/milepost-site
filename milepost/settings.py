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
import sys
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

# THE KEY THAT SIGNS LICENCE DOCUMENTS, AND IT IS NOT `SECRET_KEY`.
#
# Ed25519, base64-encoded raw private bytes. `manage.py make_licence_key`
# generates a pair, writes this half into the env file, and prints only the
# public one -- which ships inside the `homeschool-lms` release so an instance
# can verify a cached licence with no network, which is the whole reason
# §B.3's document is signed at all.
#
# Deliberately NOT defaulted, not even in development, and this is the one
# place that departs from `SECRET_KEY`'s pattern above. A throwaway signing key
# is worse than none: it produces documents that look right here and are
# rejected by every instance in the field, and it does it silently. So an unset
# key is not a startup failure -- the marketing site and the whole human
# channel run perfectly well without one -- but the licence endpoint refuses
# with a 503 that says what is missing. See `instances.licence.signing_key`.
LICENCE_SIGNING_KEY = env('LICENCE_SIGNING_KEY')

ALLOWED_HOSTS = env_list(
    'DJANGO_ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1'] if DEBUG else [],
)

# `accounts` has arrived, and with it everything the note that used to be here
# said would come with it: auth, sessions, messages, contenttypes and the
# admin. This project has a database now for the first time.
#
# `catalog` arrives here with `Listing` and `TermsAcceptance`, by the same
# rule: an app appears when it has a model, not before. `billing` and
# `instances` are still absent, still deliberately. `instances` is the one
# with a visible consequence -- there is no installation credential, so there
# is no machine channel, so a publish is a person uploading through the site
# rather than an instance pushing over §D's authenticated channel.
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'accounts',
    # Before `catalog`, because `catalog` imports it: an Acquisition names the
    # household that made it, and a download is refused before it is recorded.
    'billing',
    'catalog',
    # The machine channel. Arrives with `Installation`, by the same rule as the
    # others -- and it is the app whose absence the docstring above used to
    # name as having a visible consequence. It no longer does: an instance can
    # authenticate and ask which of its households are paid up.
    'instances',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# THE DECISION THAT CANNOT BE TAKEN LATER. Django's own documentation is blunt
# about it: changing AUTH_USER_MODEL once migrations exist that point at it is
# "significantly more difficult", and every app still to be written --
# billing, catalog, instances -- will point at it. So it is set here, in the
# commit that brings the first model, and not after.
#
# `Account`, not `User`, because §C's identity model has two kinds of person
# in it -- somebody with a marketplace login and somebody with a login on
# their family's own installation -- and calling both "user" is how that
# distinction gets lost in conversation before it gets lost in code.
AUTH_USER_MODEL = 'accounts.Account'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

ROOT_URLCONF = 'milepost.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'milepost.wsgi.application'

# Read for the first time with this commit -- see INSTALLED_APPS. The switch
# itself was fixed early on purpose: SQLite until DB_HOST is set, which is the
# entire switch to Postgres, exactly as homeschool-lms does it, so an operator
# does not have to hold two ideas about how these projects are configured.
#
# §A settles Postgres for this project rather than SQLite, for JSONB and real
# full-text search. Neither is needed by `accounts`, so development stays on
# SQLite and the first thing that needs them is the thing that should force
# the issue.
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
# THE MANIFEST IS A DEPLOYMENT ARTEFACT, AND TESTS MUST NOT NEED ONE.
#
# `CompressedManifestStaticFilesStorage` rewrites every {% static %} to a
# hashed filename read out of `staticfiles.json`, which `collectstatic`
# writes. If a name is not in that manifest it raises rather than guessing --
# which is exactly what you want in production, where a missing entry means a
# broken asset somebody should hear about immediately.
#
# It is exactly what you do not want under test. `collectstatic` has not run,
# so the manifest does not exist, so EVERY test that renders a template
# extending base.html dies with "Missing staticfiles manifest entry for
# css/site.css" -- eight of the first twenty-three tests this project ever
# had, none of them about static files.
#
# This was here before `accounts` was; the repository simply had no tests to
# trip over it, and the first ones did so immediately.
#
# Two ways to fix it are worse than this one. Relaxing `manifest_strict`
# globally would carry the loose behaviour into production and hide the
# broken-asset error the strict version exists to raise. Overriding STORAGES
# in each test class puts the fix in the place that has to be remembered,
# which is how the second test file gets it wrong.
TESTING = 'test' in sys.argv

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedStaticFilesStorage' if TESTING
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

# ...and the same run warns "No directory at: .../staticfiles/" for a related
# reason. WhiteNoise defaults `autorefresh` to `settings.DEBUG`, and Django's
# test runner forces DEBUG to False, so under test the middleware eagerly
# scans STATIC_ROOT at startup -- a directory `collectstatic` writes and no
# checkout has. Autorefresh resolves each request against the filesystem
# instead of that startup scan, which is the right behaviour for a tree whose
# static files change under you, and which no deployment ever sees.
if TESTING:
    WHITENOISE_AUTOREFRESH = True

# UPLOADED PACKS, AND WHY THERE IS NO MEDIA_URL
#
# A course pack is a file somebody else wrote. `MEDIA_ROOT` gives it somewhere
# to live; the absence of `MEDIA_URL` is the point of this block.
#
# Serving uploads from a URL prefix means the web server hands out whatever is
# under that directory, to whoever asks, without the application seeing the
# request. For content that is entitlement-gated (§B.3: a download is checked
# per household against a fresh token) that is not a hardening detail, it is
# the whole control -- a guessable path would be the entitlement check
# bypassed by typing a URL.
#
# So packs are streamed by a view that decides, and nothing serves this
# directory directly. It sits outside STATIC_ROOT for the same reason:
# `collectstatic` must never sweep an upload into the public tree.
MEDIA_ROOT = Path(env('MEDIA_ROOT', BASE_DIR / 'uploads'))

# A pack is capped at 256MB by the format itself (`MAX_UNCOMPRESSED`), but
# Django reads a file into memory before anything looks at it. These two keep
# a large upload on disk and refuse an absurd one before the format ever sees
# it -- cheap refusals first, expensive ones after.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOG_DIR = Path(env('LOG_DIR', BASE_DIR / 'logs'))

# HARDENING THAT COSTS NOTHING, SO IT IS NEVER CONDITIONAL.
#
# These do not need HTTPS and do not interfere with a test client, so putting
# them behind an `if` only creates a development environment that behaves
# unlike the deployed one. A header that is on everywhere is a header nobody
# has to remember.
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'

# HARDENING THAT NEEDS HTTPS, WHICH A TEST RUN DOES NOT HAVE.
#
# `and not TESTING` is a bug fix, not a convenience. This block read
# `if not DEBUG` alone, and DEBUG comes from `.env` -- a file every developer
# machine has and no fresh clone does. `SECURE_SSL_REDIRECT` turns every
# test-client request into a 301 and secure cookies are never returned over
# the test client's http, so on a machine without an `.env` this suite failed
# 63 of its 137 tests, none of them for a reason connected to what they test.
# It passed here, which is exactly what made it invisible.
#
# The same shape as the staticfiles switch above, and for the same reason: a
# test run is a third environment, not a variety of production, and settings
# that assume otherwise are settings nobody can run.
if not DEBUG and not TESTING:
    # A cookie that authenticates somebody must not travel in clear text, and
    # the setting that stops it is not on by default.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
