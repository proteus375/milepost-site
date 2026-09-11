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

**Replay is bounded rather than solved.** The timestamp is signed and must be
within `CLOCK_SKEW`, so a captured request is replayable for minutes rather
than forever. Closing it completely needs a nonce store, which needs the shared
cache this project does not yet have -- and the only endpoint on this channel
today is an idempotent GET, where a replay re-fetches a document the caller was
entitled to anyway. **That stops being true the moment §D's push endpoint
lands**, where a replayed upload is a duplicate listing, so the nonce store is
a prerequisite for that commit and not for this one. Adding it changes nothing
on the wire, which is why it can wait.

**The body is signed, not just the envelope.** Nothing on this channel takes a
body yet. Including its hash now means the push endpoint does not need a new
signature scheme, and a scheme change is the expensive thing here.

THE HEADER
------------
    Authorization: Milepost-HMAC installation=<uuid>, ts=<unix seconds>, sig=<hex>

and the signed string is, with real newlines:

    <METHOD>\n<path>\n<ts>\n<sha256 hex of the body, empty string hashed if none>

The method and path are in it so a signature captured from one request cannot
be replayed against a different endpoint.
"""

import hashlib
import hmac
import time

from .models import Installation

#: How far apart the two clocks may be. Five minutes is the usual figure and
#: is chosen for the usual reason: it is longer than NTP drift on a neglected
#: machine and shorter than a person noticing a captured request and using it.
CLOCK_SKEW = 300

SCHEME = 'Milepost-HMAC'


def string_to_sign(method, path, timestamp, body):
    return '\n'.join([
        method.upper(),
        path,
        str(timestamp),
        hashlib.sha256(body or b'').hexdigest(),
    ])


def sign(secret, method, path, timestamp, body=b''):
    """Also used by the tests, and by whatever client library follows.

    Exported rather than inlined into the verifier because a signing rule with
    only one implementation is a rule nobody has checked against a second
    reading of the prose above.
    """
    return hmac.new(
        secret.encode('utf-8'),
        string_to_sign(method, path, timestamp, body).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


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
    for required in ('installation', 'ts', 'sig'):
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
        request.path,
        timestamp,
        request.body,
    )
    if not hmac.compare_digest(expected, fields['sig']):
        raise Refused('Signature does not match')

    return installation
