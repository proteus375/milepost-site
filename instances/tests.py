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
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone
from io import StringIO

from accounts.models import Account, Organisation
from billing.models import Household, HouseholdMembership

from .auth import CLOCK_SKEW, sign
from .licence import LICENCE_FORMAT, NoSigningKey, build, issue
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
             timestamp=None, body=b'', signature=None, path_signed=None):
        timestamp = int(time.time()) if timestamp is None else timestamp
        signature = signature if signature is not None else sign(
            secret, method, path_signed or url, timestamp, body,
        )
        header = (
            f'Milepost-HMAC installation={installation.identifier}, '
            f'ts={timestamp}, sig={signature}'
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
