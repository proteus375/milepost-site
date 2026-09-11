"""§B.3's entitlement document, built and signed.

WHAT THIS IS FOR, STATED ONCE, BECAUSE IT IS THE THING PEOPLE GET WRONG
-------------------------------------------------------------------------
The marketplace does not need any of this to decide whether somebody may
download. It asks `billing` in process, against a row -- `catalog.views` does
exactly that. **This document exists so an installation can answer the same
question with no network at all.**

That is the whole design constraint. §B.5 keeps the offline guarantee as "an
architectural property rather than a deployment promise ... the reason the
licence design can be fail-soft at all: an LMS with no runtime dependency on
the marketplace is one where a marketplace outage cannot take a family's
records away." A signature is what lets an instance trust a cached file it
fetched days ago, and the cache is the point.

WHAT IS IN IT, AND WHAT MUST NOT BE
-------------------------------------
§B.3: "Opaque subject ids only. **No names, no email addresses, no prices, no
plan cost.**" The instance already knows which local user maps to which
subject, because it stored that link itself, so the token carries nothing that
identifies a person to a reader who does not already know.

§C.4.3 amends that rule deliberately and in one direction only: an
*organisation* name may appear, because it is a public identity and the
operator of a co-op installation self-evidently knows which co-op they are
running. **Person names still may not.**

TWO STALENESS CASES, AND THE SPLIT IS THE INSTANCE'S JOB
----------------------------------------------------------
§B.3 is emphatic that a stale *token* and an absent *subject* mean opposite
things: a token that could not be refreshed is a network problem and everyone
keeps their last-known state through a grace window; a subject missing from a
**fresh** token is a household that genuinely stopped paying, with no grace at
all. Confusing them either locks out paying families during an outage or hands
every lapsed family a free month.

Nothing here can make that distinction -- it is a property of what the instance
did with the file, not of the file. What this side owes is the two timestamps
that let the instance tell them apart, and it emits both.
"""

import base64
import json
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from billing.models import FEATURES, household_of

#: The document's own format identifier, on the convention `courselms.course/1`
#: and `courselms.coursepack/1` already set. A reader checks this before
#: anything else, so a v2 with a different shape is refused rather than
#: misread.
LICENCE_FORMAT = 'milepost.licence/1'

#: How long a document is good for. §B.3: "Short (days), with a grace period
#: past `expires_at` -- 14 to 30 days remains the right order of magnitude."
#: The grace is the instance's to apply; this is only the honest expiry.
LICENCE_DAYS = 7


class NoSigningKey(RuntimeError):
    """Raised rather than issuing something nobody can verify."""


def signing_key():
    """The Ed25519 private key, or refuse.

    Mirrors how `SECRET_KEY` is handled in settings, and for the same reason:
    the absence of a real key is a failure, never a silently generated one. A
    key made up at import time would sign documents that every instance in the
    field rejects, and it would do it quietly.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    raw = getattr(settings, 'LICENCE_SIGNING_KEY', None)
    if not raw:
        raise NoSigningKey(
            'LICENCE_SIGNING_KEY is unset. Generate one with '
            '`manage.py make_licence_key` and put it in the environment; '
            'the public half ships in the homeschool-lms release.'
        )
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw))


def public_key_b64():
    """What ships inside `homeschool-lms`. Printed by the management command."""
    from cryptography.hazmat.primitives import serialization

    public = signing_key().public_key()
    return base64.b64encode(public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )).decode('ascii')


def entitlement_for(account, installation):
    """One subject's entry, or None if they are on no household.

    None rather than an entry with `through: null`: §B.3's second staleness
    case turns on a subject being **absent** from a fresh token, and an entry
    that says "present but not entitled" is a third state the instance has no
    rule for.
    """
    household = household_of(account)
    if household is None or not household.is_entitled:
        return None

    entry = {
        'subject': str(account.subject),
        'plan': 'family',
        'through': household.entitled_through.isoformat(),
        'features': list(FEATURES),
    }

    # §C.4.3: the instance needs the organisation's name to render "publish as
    # me / publish as Oak Hill Co-op", and has no other way to learn it. Only
    # the organisation this installation is bound to, and only if this person
    # is a member of it -- which is exactly the two-layer check §C.4.3 requires
    # of a publish, answered here so the instance does not offer a choice that
    # would be refused.
    organisation = installation.organisation
    if organisation is not None and organisation.is_active:
        if organisation.can_publish(account):
            entry['publish_as'] = [{
                'id': organisation.pk,
                'name': organisation.public_name,
            }]
    return entry


def build(installation):
    """§B.3's payload for this installation, as a plain dict."""
    issued = timezone.now()
    entitlements = []
    for account in installation.linked_accounts():
        entry = entitlement_for(account, installation)
        if entry is not None:
            entitlements.append(entry)

    return {
        'format': LICENCE_FORMAT,
        'installation_id': str(installation.identifier),
        'issued_at': issued.isoformat(),
        'expires_at': (issued + timedelta(days=LICENCE_DAYS)).isoformat(),
        'entitlements': entitlements,
    }


def issue(installation):
    """The signed document an instance caches and verifies offline.

    THE SIGNED BYTES TRAVEL, RATHER THAN BEING RECONSTRUCTED. The payload goes
    over the wire base64-encoded and the signature covers exactly those bytes,
    so the verifier never has to reproduce this side's JSON formatting to check
    a signature. Canonicalisation disagreements are a classic way for a
    signature scheme to work in tests and fail across two implementations, and
    the cost of avoiding it entirely is one base64 encode.
    """
    payload = build(installation)
    encoded = base64.b64encode(
        json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    )
    signature = signing_key().sign(encoded)
    return {
        'format': LICENCE_FORMAT,
        'algorithm': 'ed25519',
        'payload': encoded.decode('ascii'),
        'signature': base64.b64encode(signature).decode('ascii'),
    }
