"""The machine channel. Nothing here renders a page or reads a session.

§A's table is the specification for this module, and its last row is the one
that shapes everything: an instance in the field **cannot be redeployed on your
schedule**. So the version is in the path from the first URL, every response is
JSON with a `format` on it, and no refusal says more than a machine can act on.

WHY THERE IS NO SESSION HERE, AND HOW THAT IS ENFORCED
--------------------------------------------------------
§A says this app has "its own URL prefix, its own auth, no shared session
middleware". Two of those three are exactly true: `instances/urls.py` is
mounted under its own versioned prefix, and `auth.py` is the only
authentication these views use.

The third needs care, because `MIDDLEWARE` in Django is global -- there is no
per-URL middleware list, and a genuinely separate stack means a second WSGI
application, which is real operational complexity for no benefit anybody can
name today. What is achievable, and what actually matters, is that the machine
channel never *participates* in a session: these views never touch
`request.user`, never write to `request.session`, and therefore never cause a
session cookie to be issued. `SessionMiddleware` only sets a cookie when the
session was modified.

That is a property worth a test rather than a comment, and
`NoSessionOnTheMachineChannelTests` asserts it: no `Set-Cookie` on any machine
response. If that test ever fails, something in a view reached for the human
channel's furniture.
"""

import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .auth import Refused, authenticate
from .licence import NoSigningKey, issue

#: One body for every authentication failure. A machine cannot act on the
#: difference between "no such installation", "wrong signature" and "clock is
#: wrong" -- it can only retry or alert a human -- and telling them apart is
#: how somebody enumerates which installation ids exist. The specific reason
#: goes to the log, where the operator who can act on it will look.
REFUSED_BODY = {
    'error': 'unauthenticated',
    'detail': 'The request was not signed by a known active installation.',
}


def machine_endpoint(view):
    """Authenticate, or refuse identically. The decorator every view here uses.

    CSRF-exempt because there is no session and no cookie to ride: CSRF defends
    a browser that attaches credentials automatically, and nothing about this
    channel does that. A signature over the method, path, timestamp and body
    cannot be produced by a page a user happened to visit.
    """

    @csrf_exempt
    def wrapper(request, *args, **kwargs):
        try:
            installation = authenticate(request)
        except Refused as refusal:
            # Logged rather than returned. See REFUSED_BODY.
            logging.getLogger('instances.auth').warning(
                'Refused a machine request to %s: %s', request.path, refusal,
            )
            return JsonResponse(REFUSED_BODY, status=401)

        installation.seen()
        request.installation = installation
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


@require_GET
@machine_endpoint
def licence(request):
    """The entitlement document for this installation. §B.3.

    A GET, because it is a read of current state and an instance polls it
    daily. Nothing about it is a command, so nothing about it should be a POST
    -- and a GET is the shape a cache, a proxy and a person with curl all
    already understand.

    THE EMPTY ANSWER IS A REAL ANSWER. An installation whose households have
    all lapsed gets a document with an empty `entitlements` list, signed, with
    a fresh `issued_at`. It is not a 404 and not an error: §B.3's second
    staleness case is precisely "the token is fresh and this subject is absent
    from it", which the instance must read as *genuinely unentitled,
    immediately, no grace*. A refusal here would leave the instance unable to
    tell that from an outage, which is the confusion §B.3 says produces either
    a free month for everybody or a lockout for paying families.
    """
    try:
        document = issue(request.installation)
    except NoSigningKey:
        logging.getLogger('instances.licence').error(
            'A licence was requested but LICENCE_SIGNING_KEY is unset.'
        )
        # 503 rather than 500: this is a deployment that is not finished, it
        # is the operator's to fix, and an instance should retry rather than
        # treat it as a permanent answer about its entitlement.
        return JsonResponse(
            {'error': 'unavailable',
             'detail': 'Licence signing is not configured on this server.'},
            status=503,
        )
    return JsonResponse(document)
