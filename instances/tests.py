"""The machine channel, tested from the outside in.

WHAT THESE ARE FOR. Every other test suite in this project can assume a
cooperative caller: a browser that a person drove, with a session Django
issued. This one cannot. The caller is a machine holding a credential, and
half of what is worth testing is what happens when it is holding the wrong one,
the right one late, or the right one against the wrong endpoint.

The signature helper is `auth.sign`, the same function the verifier uses. That
is a deliberate weakness and worth naming: a test that signs with the
implementation cannot catch a signing rule that is wrong in both places. What
it does catch is every way the verifier can be circumvented, which is the part
an attacker has access to. The cross-implementation check is the day
`homeschool-lms` grows a client, and a payload signed by one and verified by
the other is the test that matters then.
"""

import base64
import json
import logging
import tempfile
import time
from pathlib import Path
from datetime import timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.utils import timezone
from io import StringIO

from accounts.models import Account, Organisation
from billing.models import Household, HouseholdMembership
from catalog.models import (
    Acquisition, CONTENT_LICENCE, Listing, Subject, accept_terms,
)
from catalog.packs import attach
from catalog.tests import a_pack

from .auth import CLOCK_SKEW, new_nonce, sign
from .licence import LICENCE_FORMAT, NoSigningKey, build, issue
from .views import MAX_LIMIT
from .models import Installation, InstallationLink

#: A fixed keypair, so the tests do not depend on generating one and so the
#: verifying half can be asserted against a known public key.
_KEY = Ed25519PrivateKey.generate()
SIGNING_KEY = base64.b64encode(_KEY.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)).decode('ascii')

LICENCE_URL = '/machine/v1/licence/'


class MachineFixture(TestCase):
    def setUp(self):
        super().setUp()
        # Most of these tests refuse on purpose, and each refusal is a warning
        # an operator should see in a real log and nobody should have to read
        # eight of in a test run. `RefusalsAreLoggedTests` asserts the logging
        # itself with `assertLogs`, which is the honest place for that check.
        logger = logging.getLogger('instances.auth')
        previous = logger.level
        logger.setLevel(logging.CRITICAL)
        self.addCleanup(logger.setLevel, previous)

    def person(self, handle='ada'):
        return Account.objects.create_user(
            email=f'{handle}@example.com', handle=handle,
            password='a-long-enough-passphrase',
        )

    def paid_household(self, *accounts, name='The Lovelaces', entitled=True):
        home = Household.objects.create(
            name=name,
            entitled_through=(
                timezone.localdate() + timedelta(days=30) if entitled else None
            ),
        )
        for position, account in enumerate(accounts):
            home.add_member(account, role=(
                HouseholdMembership.Role.OWNER if position == 0
                else HouseholdMembership.Role.MEMBER
            ))
        return home

    def provision(self, name='Oak Hill', organisation=None):
        """Named `provision` rather than `installation`, because `setUp`
        assigns `self.installation` and a method the fixture shadows is a
        `TypeError` three tests later."""
        return Installation.provision(name=name, organisation=organisation)

    def call(self, secret, installation, url=LICENCE_URL, method='GET',
             timestamp=None, body=b'', signature=None, path_signed=None,
             nonce=None):
        """`url` is signed whole, query string included -- which is the point
        of `auth.string_to_sign` taking a full path. A test helper that signed
        only the path would pass while the verifier was wrong."""
        timestamp = int(time.time()) if timestamp is None else timestamp
        nonce = new_nonce() if nonce is None else nonce
        signature = signature if signature is not None else sign(
            secret, method, path_signed or url, timestamp, nonce, body,
        )
        header = (
            f'Milepost-HMAC installation={installation.identifier}, '
            f'ts={timestamp}, nonce={nonce}, sig={signature}'
        )
        return self.client.generic(
            method, url, data=body, HTTP_AUTHORIZATION=header,
        )


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class AuthenticatingAMachineTests(MachineFixture):
    def setUp(self):
        super().setUp()
        self.installation, self.secret = self.provision()

    def test_a_correctly_signed_request_is_answered(self):
        self.assertEqual(self.call(self.secret, self.installation).status_code, 200)

    def test_an_unsigned_request_is_refused(self):
        self.assertEqual(self.client.get(LICENCE_URL).status_code, 401)

    def test_so_is_a_bearer_token_that_happens_to_be_the_secret(self):
        """The secret alone is not a credential on this channel. If this ever
        passes, the scheme silently became a bearer token."""
        response = self.client.get(
            LICENCE_URL, HTTP_AUTHORIZATION=f'Bearer {self.secret}',
        )
        self.assertEqual(response.status_code, 401)

    def test_a_wrong_signature_is_refused(self):
        response = self.call(self.secret, self.installation, signature='00' * 32)
        self.assertEqual(response.status_code, 401)

    def test_signing_with_the_wrong_secret_is_refused(self):
        other, other_secret = self.provision(name='Somebody else')
        response = self.call(other_secret, self.installation)
        self.assertEqual(response.status_code, 401)

    def test_an_old_timestamp_is_refused(self):
        """Bounded replay is the point of signing the timestamp. A captured
        request is good for minutes, not forever."""
        stale = int(time.time()) - CLOCK_SKEW - 60
        self.assertEqual(
            self.call(self.secret, self.installation, timestamp=stale).status_code,
            401,
        )

    def test_and_so_is_one_from_the_future(self):
        ahead = int(time.time()) + CLOCK_SKEW + 60
        self.assertEqual(
            self.call(self.secret, self.installation, timestamp=ahead).status_code,
            401,
        )

    def test_a_signature_for_another_path_does_not_travel(self):
        """The path is in the signed string precisely so a signature captured
        from one endpoint cannot be replayed against another. There is only one
        endpoint today, so this is tested against a path that does not exist --
        the check has to be in place before the second endpoint makes it
        matter."""
        response = self.call(
            self.secret, self.installation, path_signed='/machine/v1/something-else/',
        )
        self.assertEqual(response.status_code, 401)

    def test_a_deactivated_installation_is_refused(self):
        self.installation.is_active = False
        self.installation.save(update_fields=['is_active'])
        self.assertEqual(self.call(self.secret, self.installation).status_code, 401)

    def test_a_rotated_secret_stops_the_old_one_immediately(self):
        """No grace window, deliberately: the reason to rotate is that the old
        secret may be in somebody else's hands."""
        old = self.secret
        new = self.installation.rotate_secret()

        self.assertEqual(self.call(old, self.installation).status_code, 401)
        self.assertEqual(self.call(new, self.installation).status_code, 200)

    def test_every_refusal_says_the_same_thing(self):
        """A machine cannot act on the difference, and telling them apart is
        how somebody enumerates which installation ids exist."""
        unknown = Installation(identifier='11111111-1111-1111-1111-111111111111')
        bodies = {
            self.client.get(LICENCE_URL).content,
            self.call(self.secret, self.installation, signature='ff' * 32).content,
            self.call(self.secret, unknown).content,
        }
        self.assertEqual(len(bodies), 1)

    def test_a_successful_call_records_that_it_was_seen(self):
        """The cheapest answer to "is this deployment still talking to us",
        which is the first question anybody asks when a customer reports that
        nothing syncs."""
        self.assertIsNone(self.installation.last_seen_at)
        self.call(self.secret, self.installation)
        self.installation.refresh_from_db()
        self.assertIsNotNone(self.installation.last_seen_at)

    def test_a_refused_call_does_not(self):
        self.client.get(LICENCE_URL)
        self.installation.refresh_from_db()
        self.assertIsNone(self.installation.last_seen_at)


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class NoSessionOnTheMachineChannelTests(MachineFixture):
    """§A: "its own URL prefix, its own auth, no shared session middleware".

    `MIDDLEWARE` is global in Django and a genuinely separate stack means a
    second WSGI application, which is real operational complexity for no
    benefit anybody can name today. What is achievable and what actually
    matters is that this channel never participates in a session -- and that is
    a property a test can hold, where a comment cannot.
    """

    def test_no_cookie_is_ever_set(self):
        installation, secret = self.provision()
        response = self.call(secret, installation)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Set-Cookie', response)
        self.assertEqual(len(response.cookies), 0)

    def test_a_refusal_sets_none_either(self):
        response = self.client.get(LICENCE_URL)
        self.assertEqual(len(response.cookies), 0)

    def test_a_browser_session_does_not_authenticate_here(self):
        """The reverse test, which §E.7.1 says is the direction that fails: a
        signed-in staff member with a perfectly good session cookie is still
        not an installation."""
        staff = Account.objects.create_superuser(
            email='ops@example.com', handle='ops',
            password='a-long-enough-passphrase',
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(LICENCE_URL).status_code, 401)


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class WhatTheLicenceSaysTests(MachineFixture):
    def setUp(self):
        super().setUp()
        self.installation, self.secret = self.provision()

    def document(self):
        response = self.call(self.secret, self.installation)
        return json.loads(response.content)

    def payload(self):
        return json.loads(base64.b64decode(self.document()['payload']))

    def link(self, account):
        return InstallationLink.objects.create(
            installation=self.installation, account=account,
        )

    def test_it_is_signed_by_the_key_the_instance_will_hold(self):
        """The whole point of the document. An instance verifies a file it
        cached days ago, with no network, which is what keeps a marketplace
        outage from taking a family's records away (§B.5)."""
        document = self.document()
        public = _KEY.public_key()

        public.verify(
            base64.b64decode(document['signature']),
            document['payload'].encode('ascii'),
        )  # raises InvalidSignature if wrong

    def test_a_tampered_payload_fails_verification(self):
        document = self.document()
        forged = base64.b64encode(
            json.dumps({'entitlements': [{'subject': 'anybody'}]}).encode()
        )
        with self.assertRaises(InvalidSignature):
            _KEY.public_key().verify(
                base64.b64decode(document['signature']), forged,
            )

    def test_it_names_its_own_format(self):
        """Checked before anything else by a reader, so a v2 with a different
        shape is refused rather than misread. The convention `courselms.course/1`
        already set."""
        self.assertEqual(self.document()['format'], LICENCE_FORMAT)
        self.assertEqual(self.payload()['format'], LICENCE_FORMAT)

    def test_an_entitled_household_appears_by_subject(self):
        ada = self.person('ada')
        self.paid_household(ada)
        self.link(ada)

        entry = self.payload()['entitlements'][0]
        self.assertEqual(entry['subject'], str(ada.subject))
        self.assertIn('marketplace.download', entry['features'])

    def test_the_payload_carries_no_name_and_no_email(self):
        """§B.3: "Opaque subject ids only. No names, no email addresses, no
        prices, no plan cost." The instance already knows which local user maps
        to which subject, because it stored that link itself."""
        ada = self.person('ada')
        self.paid_household(ada)
        self.link(ada)

        raw = base64.b64decode(self.document()['payload']).decode()
        self.assertNotIn('ada@example.com', raw)
        self.assertNotIn('"ada"', raw)
        self.assertNotIn('The Lovelaces', raw)

    def test_a_lapsed_household_is_absent_rather_than_marked(self):
        """§B.3's second staleness case turns on a subject being ABSENT from a
        fresh token, which the instance reads as genuinely unentitled with no
        grace. An entry saying "present but not entitled" is a third state
        nothing has a rule for."""
        ada = self.person('ada')
        self.paid_household(ada, entitled=False)
        self.link(ada)

        self.assertEqual(self.payload()['entitlements'], [])

    def test_somebody_on_no_household_is_absent_too(self):
        self.link(self.person('ada'))
        self.assertEqual(self.payload()['entitlements'], [])

    def test_an_empty_answer_is_still_a_signed_document(self):
        """Not a 404 and not an error. A refusal would leave the instance
        unable to tell "nobody here is paying" from an outage, which is the
        confusion §B.3 says produces either a free month for everybody or a
        lockout for paying families."""
        response = self.call(self.secret, self.installation)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payload()['entitlements'], [])
        self.assertIn('issued_at', self.payload())

    def test_it_carries_both_timestamps(self):
        """The instance must track token freshness separately from per-subject
        entitlement, and only the first is graced. Nothing here can make that
        distinction -- what this side owes is the two timestamps that let the
        instance make it."""
        payload = self.payload()
        self.assertIn('issued_at', payload)
        self.assertIn('expires_at', payload)
        self.assertGreater(payload['expires_at'], payload['issued_at'])

    def test_only_this_installation_s_people_are_in_it(self):
        """The reverse test. A licence that carried every entitled account on
        the marketplace would hand each installation a list of everybody who
        pays, which is both a leak and an entitlement anybody could claim."""
        mine, theirs = self.person('mine'), self.person('theirs')
        self.paid_household(mine, name='Mine')
        self.paid_household(theirs, name='Theirs')
        self.link(mine)

        subjects = [e['subject'] for e in self.payload()['entitlements']]
        self.assertEqual(subjects, [str(mine.subject)])


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class PublishingAsTheCoOpTests(MachineFixture):
    """§C.4.3: the instance needs the organisation's name to offer "publish as
    me / publish as Oak Hill Co-op", and has no other way to learn it.

    §C.4.3 also amends §B.3's no-names rule in one direction and one only: an
    organisation name may travel, because it is a public identity and the
    operator of a co-op installation self-evidently knows which co-op they are
    running. Person names still may not.
    """

    def setUp(self):
        super().setUp()
        self.priya = self.person('priya')
        self.co_op = Organisation(slug='oak-hill', name='Oak Hill Co-op')
        self.co_op.full_clean()
        self.co_op.save()
        self.installation, self.secret = self.provision(organisation=self.co_op)
        self.paid_household(self.priya, name='The Priyas')
        InstallationLink.objects.create(
            installation=self.installation, account=self.priya,
        )

    def entry(self):
        response = self.call(self.secret, self.installation)
        payload = json.loads(base64.b64decode(json.loads(response.content)['payload']))
        return payload['entitlements'][0]

    def test_a_member_is_told_they_may_publish_as_the_co_op(self):
        self.co_op.add_member(self.priya)
        self.assertEqual(
            self.entry()['publish_as'], [{'id': self.co_op.pk, 'name': 'Oak Hill Co-op'}],
        )

    def test_a_non_member_is_not(self):
        """Both layers of §C.4.3, answered here so the instance does not offer
        a choice the marketplace would refuse."""
        self.assertNotIn('publish_as', self.entry())

    def test_nor_is_anybody_when_the_organisation_has_closed(self):
        self.co_op.add_member(self.priya)
        self.co_op.is_active = False
        self.co_op.save(update_fields=['is_active'])
        self.assertNotIn('publish_as', self.entry())

    def test_a_family_installation_offers_nothing_to_publish_as(self):
        family, secret = self.provision(name='The Hydes')
        ada = self.person('ada')
        self.paid_household(ada, name='The Hydes household')
        InstallationLink.objects.create(installation=family, account=ada)

        response = self.call(secret, family)
        payload = json.loads(base64.b64decode(json.loads(response.content)['payload']))
        self.assertNotIn('publish_as', payload['entitlements'][0])


class WithoutASigningKeyTests(MachineFixture):
    """An unconfigured deployment refuses in a way an instance can act on."""

    def setUp(self):
        super().setUp()
        logger = logging.getLogger('instances.licence')
        previous = logger.level
        logger.setLevel(logging.CRITICAL)
        self.addCleanup(logger.setLevel, previous)

    @override_settings(LICENCE_SIGNING_KEY=None)
    def test_the_endpoint_says_unavailable_rather_than_failing(self):
        """503, not 500 and not 401. This is the operator's to fix and the
        instance should retry, rather than treat it as a permanent answer about
        its own entitlement."""
        installation, secret = self.provision()
        self.assertEqual(self.call(secret, installation).status_code, 503)

    @override_settings(LICENCE_SIGNING_KEY=None)
    def test_issuing_refuses_outright(self):
        """A throwaway key would be worse than none: it produces documents that
        look right here and are rejected by every instance in the field."""
        installation, _ = self.provision()
        with self.assertRaises(NoSigningKey):
            issue(installation)

    @override_settings(LICENCE_SIGNING_KEY=None)
    def test_but_the_payload_itself_needs_no_key(self):
        """Building and signing are separate so the first is testable and the
        second is the only thing that needs configuration."""
        installation, _ = self.provision()
        self.assertEqual(build(installation)['entitlements'], [])


class ProvisioningTests(MachineFixture):
    def test_a_secret_is_returned_once_and_not_shown_again(self):
        installation, secret = self.provision()
        self.assertTrue(secret)
        self.assertEqual(installation.signing_key, secret)

    def test_two_installations_do_not_share_one(self):
        _, first = self.provision(name='One')
        _, second = self.provision(name='Two')
        self.assertNotEqual(first, second)

    def test_the_identifier_is_not_the_primary_key(self):
        """It travels -- it is what the machine authenticates as and it is
        inside every licence. A sequential id would say how many installations
        exist and let somebody guess the next."""
        installation, _ = self.provision()
        self.assertNotEqual(str(installation.identifier), str(installation.pk))

    def test_an_account_links_to_an_installation_once(self):
        installation, _ = self.provision()
        ada = self.person('ada')
        InstallationLink.objects.create(installation=installation, account=ada)

        with self.assertRaises(IntegrityError), transaction.atomic():
            InstallationLink.objects.create(installation=installation, account=ada)

    def test_but_may_link_to_two_installations(self):
        """A guardian can belong to a co-op and run their own instance, and
        both deployments legitimately need to know they are entitled. This
        opens nothing: entitlement is the household's, and appearing in two
        licence payloads does not make it two subscriptions."""
        co_op, _ = self.provision(name='Oak Hill')
        home, _ = self.provision(name='Home')
        ada = self.person('ada')

        InstallationLink.objects.create(installation=co_op, account=ada)
        InstallationLink.objects.create(installation=home, account=ada)
        self.assertEqual(ada.installation_links.count(), 2)

    def test_an_organisation_with_an_installation_cannot_be_deleted(self):
        """PROTECT, because an organisation is deactivated rather than deleted
        and an installation bound to a deleted one may publish as nobody."""
        co_op = Organisation(slug='oak-hill', name='Oak Hill Co-op')
        co_op.full_clean()
        co_op.save()
        self.provision(organisation=co_op)

        with self.assertRaises(ProtectedError):
            co_op.delete()


class SubjectIdTests(MachineFixture):
    """§C.1's join key, which is the thing that makes the bridge sound."""

    def test_every_account_gets_one(self):
        self.assertIsNotNone(self.person('ada').subject)

    def test_and_they_differ(self):
        self.assertNotEqual(self.person('ada').subject, self.person('priya').subject)

    def test_it_survives_an_email_change(self):
        """An instance stores this against a local user. A value that moved
        when somebody changed their email would silently unlink every
        guardian -- which is the Defect 1 problem, reintroduced."""
        ada = self.person('ada')
        before = ada.subject
        ada.email = 'ada-new@example.com'
        ada.save()
        ada.refresh_from_db()
        self.assertEqual(ada.subject, before)


class MakeLicenceKeyCommandTests(TestCase):
    """The command is the only supported way to make one of these, so what it
    produces has to round-trip -- and what it *discloses* has to stay put.

    The disclosure half is not hypothetical. The first version of this command
    printed the private key to stdout behind a warning, and in a workflow built
    on pasting terminal output it was pasted into a chat transcript twice. The
    ergonomics were the defect. `test_the_private_half_is_never_printed` is the
    regression test for that, and it is the one worth keeping if the others
    ever become inconvenient.
    """

    def setUp(self):
        super().setUp()
        self.env = Path(tempfile.mkdtemp()) / '.env'

    def run_command(self, **options):
        out = StringIO()
        call_command('make_licence_key', env_file=str(self.env), stdout=out,
                     **options)
        return out.getvalue()

    def written_key(self):
        line = [
            line for line in self.env.read_text().splitlines()
            if line.startswith('LICENCE_SIGNING_KEY=')
        ][0]
        return line.split('=', 1)[1]

    def test_the_pair_it_makes_round_trips(self):
        """A key generated by a snippet somebody found, with the encoding
        subtly wrong, works here and produces signatures no instance can
        verify."""
        printed = self.run_command()
        public_b64 = [
            line for line in printed.splitlines()
            if line.startswith('LICENCE_PUBLIC_KEY=')
        ][0].split('=', 1)[1]

        key = Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(self.written_key()),
        )
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        public.verify(key.sign(b'a licence document'), b'a licence document')

    def test_the_private_half_is_never_printed(self):
        """The regression test. A warning above a printed secret does not
        change what a terminal buffer is."""
        printed = self.run_command()
        self.assertNotIn(self.written_key(), printed)
        self.assertNotIn('LICENCE_SIGNING_KEY=', printed)

    def test_it_writes_into_an_env_file_that_does_not_exist_yet(self):
        self.assertFalse(self.env.exists())
        self.run_command()
        self.assertTrue(self.written_key())

    def test_it_fills_in_the_blank_line_env_example_ships(self):
        """`.env.example` carries `LICENCE_SIGNING_KEY=` with no value, so a
        fresh copy of it must not read as already configured."""
        self.env.write_text('DJANGO_DEBUG=1\nLICENCE_SIGNING_KEY=\n')
        self.run_command()

        self.assertTrue(self.written_key())
        self.assertIn('DJANGO_DEBUG=1', self.env.read_text())

    def test_it_replaces_rather_than_appending(self):
        """Two lines, where the second silently wins, is the kind of file
        somebody reads once and loses an afternoon to."""
        self.env.write_text('LICENCE_SIGNING_KEY=\n')
        self.run_command()

        lines = [
            line for line in self.env.read_text().splitlines()
            if line.startswith('LICENCE_SIGNING_KEY=')
        ]
        self.assertEqual(len(lines), 1)

    def test_it_refuses_to_replace_a_key_that_is_in_use(self):
        """Every licence signed with the old one stops verifying, and every
        instance keeps rejecting the new ones until it picks up a release
        carrying the new public half."""
        self.run_command()
        first = self.written_key()

        with self.assertRaises(CommandError) as refused:
            self.run_command()
        self.assertIn('--force', str(refused.exception))
        self.assertEqual(self.written_key(), first)

    def test_unless_asked_to(self):
        self.run_command()
        first = self.written_key()
        self.run_command(force=True)
        self.assertNotEqual(self.written_key(), first)


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class RefusalsAreLoggedTests(MachineFixture):
    """The reason a refusal says nothing useful to the caller is that it says
    it to the operator instead. If that stopped happening, every one of these
    would be an unauthenticated request nobody could investigate."""

    def test_the_specific_reason_reaches_the_log(self):
        logger = logging.getLogger('instances.auth')
        logger.setLevel(logging.NOTSET)
        installation, secret = self.provision()

        with self.assertLogs('instances.auth', level='WARNING') as logged:
            self.call(secret, installation, signature='ab' * 32)

        self.assertIn('Signature does not match', logged.output[0])


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class TheQueryStringIsSignedTests(MachineFixture):
    """The gap the pull endpoint exposed, and the regression test for it.

    v1 signed `request.path`, which Django defines as excluding the query
    string. With one parameterless endpoint that was indistinguishable from
    correct. The moment a download had to name WHICH guardian was asking, it
    became a field an attacker holding a captured request could re-point at any
    other subject on the same installation, inside the replay window.
    """

    def setUp(self):
        super().setUp()
        self.installation, self.secret = self.provision()

    def test_changing_a_parameter_invalidates_the_signature(self):
        signed_for = '/machine/v1/plans/anything/pack/?subject=aaaa'
        tampered = '/machine/v1/plans/anything/pack/?subject=bbbb'
        timestamp, nonce = int(time.time()), new_nonce()
        header = (
            f'Milepost-HMAC installation={self.installation.identifier}, '
            f'ts={timestamp}, nonce={nonce}, '
            f'sig={sign(self.secret, "GET", signed_for, timestamp, nonce, b"")}'
        )

        self.assertEqual(
            self.client.get(tampered, HTTP_AUTHORIZATION=header).status_code,
            401,
        )

    def test_while_the_signed_one_gets_past_authentication(self):
        """A 403 rather than a 401: authentication succeeded and the subject
        is simply not linked here. Proving the signature was accepted is the
        point -- a 401 would mean this test proved nothing about signing."""
        signed_for = '/machine/v1/plans/anything/pack/?subject=aaaa'
        timestamp, nonce = int(time.time()), new_nonce()
        header = (
            f'Milepost-HMAC installation={self.installation.identifier}, '
            f'ts={timestamp}, nonce={nonce}, '
            f'sig={sign(self.secret, "GET", signed_for, timestamp, nonce, b"")}'
        )

        self.assertEqual(
            self.client.get(signed_for, HTTP_AUTHORIZATION=header).status_code,
            403,
        )


@override_settings(LICENCE_SIGNING_KEY=SIGNING_KEY)
class BrowsingFromAnInstanceTests(MachineFixture):
    """§C.6's rule on the machine channel: browse freely, link to acquire.

    §B.3 removed `marketplace.browse` from the feature list deliberately --
    gating the shop window "would mean asking someone to open an account to
    find out whether they want one".
    """

    def setUp(self):
        super().setUp()
        self.installation, self.secret = self.provision()
        self.ada = self.person('ada')
        accept_terms(self.ada, accepted_by=self.ada)

    def published(self, slug='botany', with_pack=True):
        plan = Listing.objects.create(
            title='A Year of Botany', slug=slug,
            summary='Thirty-six weeks of plants, mostly outdoors.',
            subject=Subject.SCIENCE, grade_min=3, grade_max=6,
            owner_account=self.ada,
        )
        if with_pack:
            plan = attach(plan, a_pack())
        return plan.publish(by=self.ada)

    def listing_json(self, url='/machine/v1/plans/'):
        return json.loads(self.call(self.secret, self.installation, url=url).content)

    def test_an_installation_with_no_entitlement_at_all_may_browse(self):
        """Nobody is linked to this installation and nobody is paying. The
        catalogue is still the shop window."""
        self.published()
        body = self.listing_json()

        self.assertEqual(body['total'], 1)
        self.assertEqual(body['plans'][0]['slug'], 'botany')

    def test_a_stranger_with_no_credential_may_not(self):
        """Free to browse is not free to reach. The installation credential is
        what gets you to the shop window at all."""
        self.published()
        self.assertEqual(self.client.get('/machine/v1/plans/').status_code, 401)

    def test_a_draft_is_not_in_the_catalogue(self):
        Listing.objects.create(
            title='Not yet', slug='not-yet', summary='x',
            subject=Subject.SCIENCE, owner_account=self.ada,
        )
        self.assertEqual(self.listing_json()['total'], 0)

    def test_nor_is_it_reachable_by_name(self):
        Listing.objects.create(
            title='Not yet', slug='not-yet', summary='x',
            subject=Subject.SCIENCE, owner_account=self.ada,
        )
        response = self.call(
            self.secret, self.installation, url='/machine/v1/plans/not-yet/',
        )
        self.assertEqual(response.status_code, 404)

    def test_the_listing_carries_what_an_instance_needs_to_decide(self):
        self.published()
        plan = self.listing_json()['plans'][0]

        self.assertEqual(plan['version'], '1')
        self.assertEqual(plan['licence'], CONTENT_LICENCE)
        self.assertTrue(plan['has_pack'])
        self.assertTrue(plan['pack_sha256'])
        self.assertEqual(plan['owner'], 'ada')

    def test_it_carries_no_email_address(self):
        """The same rule as the licence payload. A handle is already public; an
        email address is a credential."""
        self.published()
        raw = self.call(self.secret, self.installation).content.decode()
        self.assertNotIn('ada@example.com', raw)

    def test_the_page_size_is_capped(self):
        for n in range(3):
            self.published(slug=f'plan-{n}')
        body = self.listing_json('/machine/v1/plans/?limit=2')

        self.assertEqual(len(body['plans']), 2)
        self.assertEqual(body['total'], 3)

    def test_an_absurd_limit_is_clamped_rather_than_honoured(self):
        self.published()
        body = self.listing_json('/machine/v1/plans/?limit=100000')
        self.assertEqual(body['limit'], MAX_LIMIT)

    def test_a_nonsense_limit_is_a_400(self):
        response = self.call(
            self.secret, self.installation, url='/machine/v1/plans/?limit=soon',
        )
        self.assertEqual(response.status_code, 400)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), LICENCE_SIGNING_KEY=SIGNING_KEY)
class PullingAPackTests(MachineFixture):
    """§D's pull, which is the first endpoint on this channel that says no."""

    def setUp(self):
        super().setUp()
        self.installation, self.secret = self.provision()
        self.ada = self.person('ada')
        accept_terms(self.ada, accepted_by=self.ada)
        self.plan = attach(
            Listing.objects.create(
                title='A Year of Botany', slug='botany',
                summary='Thirty-six weeks of plants.', subject=Subject.SCIENCE,
                owner_account=self.ada,
            ),
            a_pack(),
        ).publish(by=self.ada)
        self.priya = self.person('priya')

    def entitled(self, account, linked=True, paying=True):
        self.paid_household(account, name=f'The {account.handle}s',
                            entitled=paying)
        if linked:
            InstallationLink.objects.create(
                installation=self.installation, account=account,
            )
        return account

    def fetch(self, account, slug='botany'):
        url = f'/machine/v1/plans/{slug}/pack/?subject={account.subject}'
        return self.call(self.secret, self.installation, url=url)

    def test_an_entitled_linked_guardian_gets_the_bytes(self):
        self.entitled(self.priya)
        response = self.fetch(self.priya)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Milepost-Pack-Sha256'], self.plan.pack_sha256)
        self.assertEqual(response['X-Milepost-Pack-Version'], '1')

    def test_and_it_is_recorded_as_an_acquisition(self):
        """The row a review stands on, written before the bytes go out, on the
        same reasoning the web download uses."""
        self.entitled(self.priya)
        self.fetch(self.priya)

        self.assertTrue(
            Acquisition.objects.filter(
                listing=self.plan, account=self.priya,
            ).exists(),
        )

    def test_a_subject_linked_to_another_installation_is_refused(self):
        """Subject ids travel -- they are in every licence document. A linked
        account is the only thing that makes "who is asking" mean anything on a
        channel that authenticates a machine."""
        self.entitled(self.priya, linked=False)
        other, _ = self.provision(name='Somebody else')
        InstallationLink.objects.create(installation=other, account=self.priya)

        self.assertEqual(self.fetch(self.priya).status_code, 403)

    def test_and_records_nothing(self):
        """The reverse test. A refused download that counts anyway is the
        failure that would be invisible until somebody reviewed a plan they had
        never been given."""
        self.entitled(self.priya, linked=False)
        self.fetch(self.priya)
        self.assertEqual(Acquisition.objects.count(), 0)

    def test_a_subject_that_does_not_exist_gets_the_same_answer(self):
        """Telling them apart turns this into a way to test whether a subject
        id exists."""
        linked = self.fetch(self.entitled(self.priya, linked=False))
        url = '/machine/v1/plans/botany/pack/?subject=11111111-1111-1111-1111-111111111111'
        unknown = self.call(self.secret, self.installation, url=url)

        self.assertEqual(linked.status_code, unknown.status_code)
        self.assertEqual(linked.content, unknown.content)

    def test_a_lapsed_household_gets_402_rather_than_403(self):
        """The caller is who they say they are and the request is well formed;
        what is missing is a subscription. An instance should render that
        differently from "you may not" -- one is a thing a family can fix in a
        minute."""
        self.entitled(self.priya, paying=False)
        response = self.fetch(self.priya)

        self.assertEqual(response.status_code, 402)
        self.assertIn(b'lapsed', response.content)

    def test_and_that_records_nothing_either(self):
        self.entitled(self.priya, paying=False)
        self.fetch(self.priya)
        self.assertEqual(Acquisition.objects.count(), 0)

    def test_a_download_with_no_subject_is_a_400(self):
        response = self.call(
            self.secret, self.installation, url='/machine/v1/plans/botany/pack/',
        )
        self.assertEqual(response.status_code, 400)

    def test_an_unpublished_plan_is_a_404_even_to_an_entitled_reader(self):
        self.entitled(self.priya)
        draft = Listing.objects.create(
            title='Not yet', slug='not-yet', summary='x',
            subject=Subject.SCIENCE, owner_account=self.ada,
        )
        self.assertEqual(self.fetch(self.priya, slug=draft.slug).status_code, 404)

    def test_the_author_pulling_their_own_records_no_acquisition(self):
        """An author holding their own work is not an acquisition, and the rule
        has to hold on this channel too or the same row becomes a lie depending
        on which door it came through."""
        self.entitled(self.ada)
        response = self.fetch(self.ada)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Acquisition.objects.count(), 0)

    def test_an_unauthenticated_pull_is_refused_before_any_of_this(self):
        self.entitled(self.priya)
        url = f'/machine/v1/plans/botany/pack/?subject={self.priya.subject}'
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_a_subject_that_is_not_a_uuid_is_refused_rather_than_crashing(self):
        """A UUIDField raises ValidationError, not ValueError, on text that is
        not a UUID -- so this was a 500 until a test sent one. Unparseable
        input becoming a server error on a channel anybody with a credential
        can reach is a free denial of service and a stack trace in a log."""
        url = '/machine/v1/plans/botany/pack/?subject=hello'
        self.assertEqual(
            self.call(self.secret, self.installation, url=url).status_code, 403,
        )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), LICENCE_SIGNING_KEY=SIGNING_KEY)
class PushFixture(MachineFixture):
    """§D's push: an instance publishes a plan it built.

    The thing to keep straight is that this endpoint cannot make anything
    public. §D step 4 stores it, step 5 is "moderation, then published", and
    publication is still blocked on counsel rather than on code.
    """

    def setUp(self):
        super().setUp()
        self.installation, self.secret = self.provision()
        self.priya = self.person('priya')
        self.paid_household(self.priya, name='The Priyas')
        InstallationLink.objects.create(
            installation=self.installation, account=self.priya,
        )

    def post(self, account=None, pack=None, url=None, nonce=None, **fields):
        account = account or self.priya
        payload = {
            'subject': str(account.subject),
            'title': 'A Year of Botany',
            'summary': 'Thirty-six weeks of plants, mostly outdoors.',
            'subject_area': Subject.SCIENCE,
            'grade_min': '3',
            'grade_max': '6',
        }
        payload.update({k: v for k, v in fields.items() if v is not None})
        for key in [k for k, v in fields.items() if v is None]:
            payload.pop(key, None)
        payload['pack'] = SimpleUploadedFile(
            'plan.coursepack', a_pack() if pack is None else pack,
        )

        url = url or '/machine/v1/plans/'
        timestamp = int(time.time())
        nonce = new_nonce() if nonce is None else nonce
        # A multipart body is built by the test client, so the signature has to
        # be over the bytes it will actually send. Encoding it here is the only
        # way to sign what goes out rather than what we meant to send.
        body = encode_multipart(BOUNDARY, payload)
        header = (
            f'Milepost-HMAC installation={self.installation.identifier}, '
            f'ts={timestamp}, nonce={nonce}, '
            f'sig={sign(self.secret, "POST", url, timestamp, nonce, body)}'
        )
        # `generic` rather than `post`: the test client re-encodes when the
        # content type is multipart, and the body has to reach the server as
        # the exact bytes that were signed.
        return self.client.generic(
            'POST', url, data=body, content_type=MULTIPART_CONTENT,
            HTTP_AUTHORIZATION=header,
        )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), LICENCE_SIGNING_KEY=SIGNING_KEY)
class PushingAPlanTests(PushFixture):
    """§D's push: an instance publishes a plan it built.

    The thing to keep straight is that this endpoint cannot make anything
    public. §D step 4 stores it, step 5 is "moderation, then published", and
    publication is still blocked on counsel rather than on code.
    """

    def test_a_pushed_plan_lands_for_moderation(self):
        response = self.post()

        self.assertEqual(response.status_code, 201)
        plan = Listing.objects.get()
        self.assertEqual(plan.status, Listing.Status.IN_REVIEW)
        self.assertEqual(plan.title, 'A Year of Botany')

    def test_and_is_not_visible_to_anybody(self):
        """The whole point of it not being PUBLISHED. Step 5 is moderation."""
        self.post()
        self.assertEqual(Listing.objects.visible().count(), 0)

    def test_the_pack_is_stored_and_inspected(self):
        """§D step 4: re-validated independently with this project's own copy
        of the parser, trusting nothing the uploader said about it."""
        self.post()
        plan = Listing.objects.get()

        self.assertTrue(plan.has_pack)
        self.assertTrue(plan.pack_sha256)
        self.assertEqual(plan.pack_module_count, 1)
        self.assertEqual(plan.pack_page_count, 2)

    def test_the_contributor_is_recorded_whoever_owns_it(self):
        self.post()
        self.assertEqual(Listing.objects.get().contributed_by, self.priya)

    def test_a_rubbish_pack_is_refused_and_leaves_no_listing(self):
        """Validated before anything is written. A refused pack must not leave
        a listing behind with nothing on it."""
        response = self.post(pack=b'this is not a zip')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Listing.objects.count(), 0)

    def test_an_unlinked_subject_cannot_push(self):
        stranger = self.person('stranger')
        self.paid_household(stranger, name='The Strangers')
        self.assertEqual(self.post(account=stranger).status_code, 403)

    def test_nor_can_one_whose_household_has_lapsed(self):
        """§B.3 lists `marketplace.publish` alongside `marketplace.download`.
        Publishing costs a subscription, which is also what makes §H.4's
        PUBLISHED badge cost something."""
        lapsed = self.person('lapsed')
        self.paid_household(lapsed, name='The Lapsed', entitled=False)
        InstallationLink.objects.create(
            installation=self.installation, account=lapsed,
        )
        self.assertEqual(self.post(account=lapsed).status_code, 402)

    def test_a_push_with_no_pack_is_a_400(self):
        response = self.post(pack=b'')
        self.assertEqual(response.status_code, 400)

    def test_a_reserved_title_is_refused(self):
        self.assertEqual(self.post(title='New').status_code, 400)

    def test_an_unknown_subject_area_is_refused(self):
        self.assertEqual(self.post(subject_area='VIBES').status_code, 400)

    def test_backwards_grades_are_refused_with_a_sentence(self):
        response = self.post(grade_min='9', grade_max='2')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'cannot be above', response.content)

    def test_two_plans_with_one_title_get_different_addresses(self):
        """The slug rule moved to `catalog.models` precisely so this door
        obeys it. Telling the second publisher their title is taken is a worse
        answer than giving them botany-2."""
        self.post()
        self.post()

        slugs = sorted(Listing.objects.values_list('slug', flat=True))
        self.assertEqual(slugs, ['a-year-of-botany', 'a-year-of-botany-2'])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), LICENCE_SIGNING_KEY=SIGNING_KEY)
class PushingAsTheCoOpTests(PushFixture):
    """§C.4.3's two layers, which fail for different reasons and say so."""

    def setUp(self):
        super().setUp()
        self.co_op = Organisation(slug='oak-hill', name='Oak Hill Co-op')
        self.co_op.full_clean()
        self.co_op.save()

    def bind(self):
        self.installation.organisation = self.co_op
        self.installation.save(update_fields=['organisation'])

    def test_a_member_on_a_bound_installation_publishes_as_the_co_op(self):
        self.bind()
        self.co_op.add_member(self.priya)

        self.assertEqual(self.post(publish_as='oak-hill').status_code, 201)
        plan = Listing.objects.get()
        self.assertEqual(plan.owner_organisation, self.co_op)
        self.assertIsNone(plan.owner_account)
        self.assertEqual(plan.contributed_by, self.priya)

    def test_a_member_on_an_unbound_installation_cannot(self):
        """A misconfigured deployment, and it does not say the same thing as
        the permissions failure below."""
        self.co_op.add_member(self.priya)
        response = self.post(publish_as='oak-hill')

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'not bound', response.content.lower())

    def test_a_non_member_on_a_bound_installation_cannot_either(self):
        self.bind()
        response = self.post(publish_as='oak-hill')

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'not a member', response.content.lower())

    def test_nor_can_anybody_once_the_co_op_has_closed(self):
        self.bind()
        self.co_op.add_member(self.priya)
        self.co_op.is_active = False
        self.co_op.save(update_fields=['is_active'])

        self.assertEqual(self.post(publish_as='oak-hill').status_code, 403)

    def test_naming_an_organisation_the_installation_is_not_bound_to(self):
        """Binding to one co-op does not license publishing as another."""
        self.bind()
        other = Organisation(slug='elsewhere', name='Elsewhere Co-op')
        other.full_clean()
        other.save()
        other.add_member(self.priya)

        self.assertEqual(self.post(publish_as='elsewhere').status_code, 403)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), LICENCE_SIGNING_KEY=SIGNING_KEY)
class ReplayingAPushTests(PushFixture):
    """The nonce store, which is why §D's push waited for one.

    A replayed GET re-fetches a document the caller was entitled to anyway. A
    replayed POST is a second listing, from one act of publishing.
    """

    def signed_post(self):
        """One request, built once, sendable twice. Which is the attack."""
        payload = {
            'subject': str(self.priya.subject),
            'title': 'A Year of Botany',
            'summary': 'Thirty-six weeks of plants.',
            'subject_area': Subject.SCIENCE,
            'grade_min': '3',
            'grade_max': '6',
            'pack': SimpleUploadedFile('plan.coursepack', a_pack()),
        }
        url = '/machine/v1/plans/'
        timestamp, nonce = int(time.time()), new_nonce()
        body = encode_multipart(BOUNDARY, payload)
        header = (
            f'Milepost-HMAC installation={self.installation.identifier}, '
            f'ts={timestamp}, nonce={nonce}, '
            f'sig={sign(self.secret, "POST", url, timestamp, nonce, body)}'
        )
        return lambda: self.client.generic(
            'POST', url, data=body, content_type=MULTIPART_CONTENT,
            HTTP_AUTHORIZATION=header,
        )

    def test_the_same_request_twice_creates_one_listing(self):
        send = self.signed_post()

        self.assertEqual(send().status_code, 201)
        self.assertEqual(send().status_code, 401)
        self.assertEqual(Listing.objects.count(), 1)

    def test_but_two_genuine_pushes_both_work(self):
        """The check must not refuse a client that legitimately publishes
        twice -- different bodies mean different signatures."""
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post(title='Another Year').status_code, 201)
        self.assertEqual(Listing.objects.count(), 2)

    def test_a_repeated_GET_is_not_refused(self):
        """Only unsafe methods are spent. A client retrying an identical read
        after a timeout is doing the correct thing and must not be punished
        for it."""
        timestamp, nonce = int(time.time()), new_nonce()
        signature = sign(self.secret, 'GET', LICENCE_URL, timestamp, nonce, b'')
        same = dict(timestamp=timestamp, nonce=nonce, signature=signature)

        # Byte-for-byte the same request, three times. A read is not spent.
        for _ in range(3):
            self.assertEqual(
                self.call(self.secret, self.installation, **same).status_code,
                200,
            )

    def test_a_reused_nonce_is_refused_even_with_a_different_body(self):
        """The nonce is what is spent, not the signature. A second push that
        differs in every other way but reuses the nonce is still a nonce
        somebody has already used, and the store cannot tell which of the two
        was the attacker."""
        nonce = new_nonce()
        self.assertEqual(self.post(nonce=nonce).status_code, 201)
        self.assertEqual(
            self.post(nonce=nonce, title='A Different Year').status_code, 401,
        )

    def test_two_identical_pushes_in_one_second_both_land(self):
        """The case the first draft got wrong. Using the signature as the
        nonce meant two byte-identical pushes in the same second collided, and
        the second genuine one was refused as a replay with a message saying
        it had already been used -- by somebody who had used nothing."""
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(Listing.objects.count(), 2)
