"""How a machine proves which installation it is.

§A settles the shape of this channel and the row that decides its design is
the last one: an instance in the field **cannot be redeployed on your
schedule**. Everything here is chosen to be something a deployment months
behind can still speak.

WHY A SIGNATURE RATHER THAN A BEARER TOKEN
--------------------------------------------
§A names the machine channel's authentication as "installation credential,
signed request", against a threat model of "credential theft, replay, hostile
payload". A bearer token over TLS would be simpler and is what most APIs ship,
so the reason not to is worth writing down rather than assuming.

**The credential never travels.** A bearer token is the secret, sent on every
request, and every intermediary that logs an `Authorization` header -- a proxy,
a WAF, an error tracker, a request dump in a bug report -- has logged the
credential itself. An HMAC sends a signature derived from the secret, over
material that is useless elsewhere. This is the benefit that does not depend on
anybody's threat model being right.

**Replay is bounded by the timestamp and closed by the nonce store.** The
timestamp is signed and must be within `CLOCK_SKEW`, so a captured request is
replayable for minutes rather than forever. `spend_once` closes the remaining
window for the requests where it matters, and the signature itself is the
nonce: it is unique per request by construction, so nothing extra has to be
generated, agreed on, or carried.

**Only unsafe methods are checked, and that is deliberate.** A replayed GET
re-fetches a document the caller was entitled to anyway; a replayed POST is a
duplicate listing. Spending a GET's signature would mean a client that retries
an identical request after a timeout -- which is the correct thing for a client
to do -- gets refused for it. The cost of the check lands only where the
benefit is.

**The body is signed, not just the envelope.** Nothing on this channel takes a
body yet. Including its hash now means the push endpoint does not need a new
signature scheme, and a scheme change is the expensive thing here.

THE HEADER
------------
    Authorization: Milepost-HMAC installation=<uuid>, ts=<unix seconds>,
                   nonce=<random hex>, sig=<hex>

and the signed string is, with real newlines:

    <METHOD>\n<path with query>\n<ts>\n<nonce>\n<sha256 of body, empty if none>

THE NONCE IS EXPLICIT, AND THE FIRST DRAFT TRIED TO DO WITHOUT ONE
--------------------------------------------------------------------
It used the signature itself as the nonce, on the reasoning that a signature is
unique per request already. That is true of every *distinct* request and it was
wrong, because the interesting case is not distinct: two byte-identical pushes
in the same second produce the same signature, so the second genuine one was
refused as a replay. A test publishing the same plan twice found it.

The old behaviour could have been renamed a feature -- accidental idempotency
against a double-submit -- and that would have been dressing up a bug. It
refuses a legitimate request, the refusal says "already used" to somebody who
used nothing, and it is unreproducible one second later. An explicit nonce
costs one header field and removes the case entirely.

The method and path are in it so a signature captured from one request cannot
be replayed against a different endpoint.

THE PATH INCLUDES THE QUERY STRING, AND THE FIRST VERSION DID NOT
-------------------------------------------------------------------
It signed `request.path`, which Django defines as excluding the query string.
With one endpoint taking no parameters that was indistinguishable from correct,
and it stopped being correct the moment §D's pull endpoint needed to say *which
guardian* is downloading -- a `?subject=` outside the signature is a field an
attacker holding a captured request can change, within the replay window, to
any other subject on the same installation.

Fixed here rather than worked around by moving the parameter into the path,
because the parameter is not the problem: any future endpoint with a query
string would have had the same hole, and the next person to add one would have
had no reason to suspect it. Signing `get_full_path()` closes the class.

This was free precisely because it was found before anything in the field spoke
v1. It is exactly the change the version prefix exists to make expensive later,
which is the argument for looking hard at this file now rather than after a
deployment.
"""

import hashlib
import hmac
import secrets
import time

from django.core.cache import cache

from .models import Installation

#: How far apart the two clocks may be. Five minutes is the usual figure and
#: is chosen for the usual reason: it is longer than NTP drift on a neglected
#: machine and shorter than a person noticing a captured request and using it.
CLOCK_SKEW = 300

SCHEME = 'Milepost-HMAC'


def string_to_sign(method, path, timestamp, nonce, body):
    """`path` is the full path INCLUDING the query string. See the module
    docstring -- a caller passing `request.path` here would sign less than it
    meant to, and would do it silently."""
    return '\n'.join([
        method.upper(),
        path,
        str(timestamp),
        nonce,
        hashlib.sha256(body or b'').hexdigest(),
    ])


def new_nonce():
    """What a client puts in the header. Here so both ends agree on the shape."""
    return secrets.token_hex(16)


def sign(secret, method, path, timestamp, nonce, body=b''):
    """Also used by the tests, and by whatever client library follows.

    Exported rather than inlined into the verifier because a signing rule with
    only one implementation is a rule nobody has checked against a second
    reading of the prose above.
    """
    return hmac.new(
        secret.encode('utf-8'),
        string_to_sign(method, path, timestamp, nonce, body).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


#: Methods whose replay changes something. Everything else is a read.
UNSAFE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def spend_once(installation, nonce):
    """Refuse a nonce that has already been used. Raises `Refused`.

    `cache.add` is the whole mechanism and it is chosen for being atomic: it
    writes only if the key is absent and reports which happened, so two
    concurrent replays cannot both read "not seen" and both proceed. A
    get-then-set would be a race, and the race is precisely the thing an
    attacker replaying a request is trying to win.

    Held for twice `CLOCK_SKEW`, because that is the longest a signature can
    still be inside its own window; past that the timestamp check refuses it
    anyway and remembering it longer only costs rows.

    A cache that is down fails CLOSED -- `cache.add` raising propagates, the
    request is refused, and the upload does not happen. The alternative is a
    replay window that opens exactly when the infrastructure is unhealthy,
    which is when somebody is most likely to be poking at it.
    """
    key = f'machine-nonce:{installation.identifier}:{nonce}'
    if not cache.add(key, 1, timeout=CLOCK_SKEW * 2):
        raise Refused('Signature has already been used')


class Refused(Exception):
    """Authentication failed. The message is for the operator reading a log.

    NOT for the caller: `machine_endpoint` answers every one of these with the
    same body. A machine cannot act on the difference between "no such
    installation" and "wrong secret", and telling it apart is how somebody
    enumerates which installation ids exist.
    """


def _parse(header):
    if not header or not header.startswith(SCHEME + ' '):
        raise Refused(f'Authorization header is not {SCHEME}')
    fields = {}
    for part in header[len(SCHEME) + 1:].split(','):
        key, _, value = part.strip().partition('=')
        if not key or not value:
            raise Refused('Malformed authorization header')
        fields[key.strip()] = value.strip()
    for required in ('installation', 'ts', 'nonce', 'sig'):
        if required not in fields:
            raise Refused(f'Authorization header has no {required}')
    return fields


def authenticate(request):
    """The Installation that signed this request, or raise Refused."""
    fields = _parse(request.headers.get('Authorization'))

    try:
        timestamp = int(fields['ts'])
    except ValueError:
        raise Refused('Timestamp is not an integer') from None
    if abs(time.time() - timestamp) > CLOCK_SKEW:
        raise Refused('Timestamp is outside the permitted window')

    try:
        installation = Installation.objects.select_related(
            'organisation',
        ).get(identifier=fields['installation'])
    except (Installation.DoesNotExist, ValueError, TypeError):
        raise Refused('No such installation') from None

    if not installation.is_active:
        raise Refused('Installation is not active')

    # Both ends hold the same secret; see `Installation`'s module docstring for
    # why it is stored rather than hashed, and what that costs.
    expected = sign(
        installation.signing_key,
        request.method,
        request.get_full_path(),
        timestamp,
        fields['nonce'],
        request.body,
    )
    if not hmac.compare_digest(expected, fields['sig']):
        raise Refused('Signature does not match')

    # After the signature is verified, never before: an unauthenticated caller
    # must not be able to fill the nonce store, or to burn a signature they
    # guessed at.
    if request.method in UNSAFE_METHODS:
        spend_once(installation, fields['nonce'])

    return installation
