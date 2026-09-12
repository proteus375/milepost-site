"""§C.1's layer 2: a guardian proving to their own instance who they are here.

WHERE THIS LIVES, AND THE ONE PLACE §A PULLS IN TWO DIRECTIONS
---------------------------------------------------------------
§A's app table gives `accounts` "marketplace identity, OAuth provider
endpoints, profile, organisations", so the code is here. §A also gives
`instances` "its own URL prefix, its own auth, no shared session middleware",
and this flow is the one thing in the project that is genuinely both channels
at once.

So ownership follows §A and placement follows the traffic:

| | |
| --- | --- |
| `authorize` | A person, in a browser, with a session and a consent page. Human channel, human prefix, CSRF. |
| `token` | A server-to-server POST with no human in it, from a deployment that may be months behind. Machine channel, versioned prefix, installation signature. |

Splitting them that way is not a compromise between two rules; it is what both
rules say when you notice the two legs are different kinds of request. The
token leg is an address an instance in the field constructs, which is exactly
what §A's version prefix exists for. The authorize leg is a link a browser
follows, and putting it behind machine authentication would mean asking a
browser to sign a request.

WHAT THE CLIENT GETS IS A SUBJECT, NOT AN ACCESS TOKEN
--------------------------------------------------------
See `AuthorizationCode`'s docstring. Every machine-channel request is
authenticated by the installation credential and names its subject as a
parameter, so a bearer token would be a credential with nothing to open, and
issuing one would mean two ways to authenticate the same channel.

A REFUSAL BEFORE THE REDIRECT IS VALIDATED IS SHOWN, NOT REDIRECTED
--------------------------------------------------------------------
The order of checks in `authorize` is the security-relevant part and it is the
order RFC 6749 §4.1.2.1 requires. Until the client and the redirect URI are
known good, there is nowhere safe to send an error -- redirecting to an
unverified URI is the open-redirect this endpoint would otherwise be. After
they check out, errors go back to the client as the spec describes, because by
then the destination is one an operator wrote down.
"""

import secrets
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import AuthorizationCode

#: Length of the authorization code, in bytes before encoding. It is a bearer
#: credential for five minutes, which is long enough to be worth guessing at
#: if it were short.
CODE_BYTES = 32

#: The only challenge method implemented. RFC 7636 also defines `plain`, where
#: the challenge IS the verifier; every client here is a Django application
#: that can compute a SHA-256, so supporting it would add nothing but a
#: downgrade path.
CHALLENGE_METHOD = 'S256'


def _installation_for(client_id):
    """Imported locally, deliberately.

    `instances` imports `accounts` at module level. Doing the reverse would
    make the two a cycle that happens to work because of import ordering, which
    is the kind of thing that survives until somebody adds an import.
    """
    from instances.models import Installation

    try:
        return Installation.objects.get(identifier=client_id, is_active=True)
    except (Installation.DoesNotExist, ValueError, TypeError):
        return None


def _refuse(request, reason):
    return render(request, 'accounts/oauth_refused.html', {'reason': reason},
                  status=400)


def _back_to_client(redirect_uri, **params):
    joiner = '&' if '?' in redirect_uri else '?'
    return redirect(f'{redirect_uri}{joiner}{urlencode(params)}')


@login_required
@require_http_methods(['GET', 'POST'])
def authorize(request):
    """Ask the guardian, then hand their instance a code to collect.

    `login_required` rather than a bespoke check: this is the human channel and
    a marketplace session is exactly what it means to be signed in here. A
    guardian who is not signed in gets the ordinary login page and comes back.
    """
    client_id = request.GET.get('client_id', '')
    redirect_uri = request.GET.get('redirect_uri', '')
    challenge = request.GET.get('code_challenge', '')
    method = request.GET.get('code_challenge_method', '')
    state = request.GET.get('state', '')

    installation = _installation_for(client_id)
    if installation is None:
        return _refuse(request, 'That installation is not one this site knows.')

    # THE CHECK THAT MATTERS. An authorization server that honours whatever
    # redirect a request names is an open redirect with a credential attached.
    # The comparison is exact rather than prefix-based: a prefix match is how
    # `https://real.example/` comes to match `https://real.example.attacker.dev/`.
    if not installation.redirect_uri or redirect_uri != installation.redirect_uri:
        return _refuse(
            request,
            'That installation did not ask to be sent anywhere this site '
            'recognises. Nothing has been shared.',
        )

    # From here the destination is one an operator wrote down, so errors can
    # travel back to the client rather than dead-ending in front of a person
    # who cannot act on them.
    if method != CHALLENGE_METHOD or not challenge:
        return _back_to_client(
            redirect_uri, error='invalid_request', state=state,
            error_description=f'code_challenge_method must be {CHALLENGE_METHOD}.',
        )

    if request.method == 'GET':
        return render(request, 'accounts/oauth_authorize.html', {
            'installation': installation,
            'params': request.GET.urlencode(),
        })

    if request.POST.get('decision') != 'allow':
        # A refusal is a real answer and the client is told so, rather than
        # being left to time out and guess.
        return _back_to_client(
            redirect_uri, error='access_denied', state=state,
        )

    code = AuthorizationCode.objects.create(
        code=secrets.token_urlsafe(CODE_BYTES),
        installation=installation,
        account=request.user,
        code_challenge=challenge,
        redirect_uri=redirect_uri,
    )
    return _back_to_client(redirect_uri, code=code.code, state=state)


def token(request):
    """Exchange a code for the subject it stands for, and record the link.

    Wrapped by `instances.views.machine_endpoint` where it is mounted, so by
    the time this runs the installation has proved itself with a signature and
    the request's nonce has been spent. That is why there is no client secret
    in the body: the request is already authenticated, and a secret in a POST
    body would be a second credential doing the first one's job.

    Every refusal is `invalid_grant` with no detail, and that is the RFC's
    advice as well as this project's habit on the machine channel: a client
    cannot act on the difference between an expired code, a spent one, a wrong
    verifier and a code belonging to somebody else, and the differences are
    exactly what an attacker probing with a stolen code would want.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'invalid_request'}, status=405)
    if request.POST.get('grant_type') != 'authorization_code':
        return JsonResponse({'error': 'unsupported_grant_type'}, status=400)

    presented = request.POST.get('code', '')
    verifier = request.POST.get('code_verifier', '')
    redirect_uri = request.POST.get('redirect_uri', '')

    found = AuthorizationCode.objects.select_related(
        'account', 'installation',
    ).filter(code=presented).first()

    refused = JsonResponse({'error': 'invalid_grant'}, status=400)
    if found is None or not found.is_spendable:
        return refused
    # The code belongs to whoever it was issued to. Without this an
    # installation could redeem a code issued for a different one, which is the
    # whole reason the code names its client.
    if found.installation_id != request.installation.pk:
        return refused
    if redirect_uri != found.redirect_uri:
        return refused
    if not verifier or not found.verifies(verifier):
        return refused

    found.redeemed_at = timezone.now()
    found.save(update_fields=['redeemed_at'])

    # §C.1's whole product: the instance now knows which marketplace identity
    # its local user is, and this installation may act for them.
    from instances.models import InstallationLink

    InstallationLink.objects.get_or_create(
        installation=found.installation, account=found.account,
    )

    return JsonResponse({
        'format': 'milepost.identity/1',
        'subject': str(found.account.subject),
        # The handle is public by construction -- it is in the URL of their
        # profile page -- and the instance needs something to show a guardian
        # so they can see which account they linked. The email address is not
        # here and must not be: it is a credential, and §B.3's rule about what
        # crosses this channel is not suspended because a person consented to
        # the linking.
        'handle': found.account.handle,
    })
