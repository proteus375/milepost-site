"""Settings that differ between a deployment, a development machine and a test.

WHY THIS FILE EXISTS. Twice now the same bug has been found in these two
projects, and both times by running the suite somewhere other than the machine
that wrote it.

Settings branch on `DEBUG`, `DEBUG` is read from `.env`, and `.env` is a file
every developer machine has and no fresh clone, CI runner or new laptop does.
Django's test runner sets `DEBUG = False` for the run -- but only after this
module has been imported and every branch already taken. So a suite that
passes here can fail dozens of tests anywhere else, for reasons that have
nothing to do with what those tests are about: a staticfiles manifest that was
never collected, or an SSL redirect turning every request into a 301.

There are three environments, not two. Production, development, and a test
run, which is not a variety of either. These tests hold each of the three to
what it is supposed to be, and they reload the settings module to do it
because `override_settings` can set a value but cannot show that the value
came from the branch an operator depends on.
"""

import importlib
import os
import sys
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from milepost import settings as settings_module


NAME = 'milepost.settings'


def reloaded(*, as_served=False, **environment):
    """Import settings afresh with these environment variables set.

    `as_served=True` also hides `sys.argv`, and that is the part worth
    naming. Settings branch on the environment AND on whether this process is
    a test run. A reload that patches only the environment simulates half a
    production import -- and the half it leaves behind is the half that says
    "you are a test", which is precisely the half these tests exist to check.

    A FRESH MODULE, NOT `importlib.reload`. Reload executes into the module's
    existing namespace, so a name set by one pass survives a pass that does
    not reassign it -- and every setting here is inside an `if`. The first
    version of these tests read `SECURE_SSL_REDIRECT = True` in the
    development case, left behind by the production case that ran before it,
    and reported a redirect nothing had configured. Dropping the cached
    module gives each call an empty namespace, which is the only way an
    absent setting reads as absent.
    """
    additions = {k: v for k, v in environment.items() if v is not None}
    removals = [k for k, v in environment.items() if v is None]
    # A KEY, BECAUSE THIS IS NOT THE TEST FOR THE KEY. These settings refuse
    # to import at all with DEBUG off and no DJANGO_SECRET_KEY -- correct, and
    # exactly what a developer machine looks like, since a key is only
    # required when DEBUG is off and a local `.env` therefore has none to
    # inherit. Without this default, every simulated production import dies on
    # the key check before reaching the hardening these tests are about, and
    # the failure appears only on machines whose `.env` omits the key. Which
    # is to say: the same class of bug this whole file exists to catch, one
    # level up.
    additions.setdefault('DJANGO_SECRET_KEY', 'throwaway-for-a-settings-reload')
    argv = ['manage.py', 'runserver'] if as_served else sys.argv
    cached = sys.modules.pop(NAME, None)

    try:
        with patch.dict(os.environ, additions), patch.object(sys, 'argv', argv):
            for key in removals:
                os.environ.pop(key, None)
            return importlib.import_module(NAME)
    finally:
        # Put the real one back, so nothing downstream imports a module built
        # under a patched environment.
        if cached is not None:
            sys.modules[NAME] = cached


class AlwaysOnHardeningTests(SimpleTestCase):
    """Whatever the environment. A header nobody has to remember."""

    def test_content_type_sniffing_is_off(self):
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_the_session_cookie_is_not_readable_by_script(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_framing_is_denied(self):
        self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY')


class ProductionHardeningTests(SimpleTestCase):
    def test_a_deployment_redirects_to_https_and_pins_it(self):
        module = reloaded(DJANGO_DEBUG='False', as_served=True)

        self.assertTrue(module.SECURE_SSL_REDIRECT)
        self.assertTrue(module.SESSION_COOKIE_SECURE)
        self.assertTrue(module.CSRF_COOKIE_SECURE)
        self.assertTrue(module.SECURE_HSTS_SECONDS)
        self.assertEqual(
            module.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'),
        )

    def test_and_uses_the_hashed_manifest_storage(self):
        module = reloaded(DJANGO_DEBUG='False', as_served=True)
        self.assertIn('Manifest', module.STORAGES['staticfiles']['BACKEND'])

    def test_development_does_neither(self):
        """The redirect would break a local http server and the manifest
        would need `collectstatic` after every CSS edit."""
        module = reloaded(DJANGO_DEBUG='True')

        self.assertFalse(getattr(module, 'SECURE_SSL_REDIRECT', False))
        self.assertNotIn('Manifest', module.STORAGES['staticfiles']['BACKEND'])


class ATestRunIsItsOwnEnvironmentTests(SimpleTestCase):
    """The regression these two tests exist for.

    Both assertions failed on any machine without an `.env` before the fix,
    and passed on the machine that wrote them. That is the whole shape of the
    bug: a green suite was evidence about one laptop.
    """

    def test_debug_off_does_not_turn_on_the_ssl_redirect_under_test(self):
        module = reloaded(DJANGO_DEBUG='False')
        self.assertFalse(getattr(module, 'SECURE_SSL_REDIRECT', False))

    def test_nor_secure_cookies_the_test_client_will_never_send(self):
        module = reloaded(DJANGO_DEBUG='False')
        self.assertFalse(getattr(module, 'SESSION_COOKIE_SECURE', False))

    def test_nor_the_manifest_storage_no_collectstatic_has_written(self):
        module = reloaded(DJANGO_DEBUG='False')
        self.assertNotIn('Manifest', module.STORAGES['staticfiles']['BACKEND'])

    def test_and_the_switch_is_what_does_it(self):
        self.assertTrue(settings_module.TESTING)
