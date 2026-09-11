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

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from accounts.models import Account
from billing.models import entitlement_refusal
from catalog.models import (
    GRADE_MAX, GRADE_MIN, RESERVED_SLUGS, Listing, Subject,
    record_acquisition, slug_for, unique_slug,
)
from catalog.packs import attach

from .auth import Refused, authenticate
from .licence import NoSigningKey, issue
from .models import InstallationLink

#: What the catalogue endpoints answer with. Named and versioned like every
#: other document that crosses this channel, so a reader checks before it
#: parses.
CATALOGUE_FORMAT = 'milepost.catalogue/1'

#: A page of listings. Deliberately a limit and an offset rather than a cursor:
#: the catalogue is small, an offset is something anybody can reason about, and
#: a cursor is what this becomes when the volume makes offsets wrong. Saying so
#: is cheaper than building the cursor now and cheaper than discovering the
#: limit by hitting it.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

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


def _plan_json(plan):
    """One listing, as the machine channel describes it.

    Deliberately not the same shape as the web page. A page renders prose for a
    parent; this is what an instance needs to decide whether to fetch the pack
    and to show a list before it does -- which is the same information §C.6
    says browsing may show without anybody linking an account.
    """
    return {
        'slug': plan.slug,
        'title': plan.title,
        'summary': plan.summary,
        'subject': plan.subject,
        'grade_min': plan.grade_min,
        'grade_max': plan.grade_max,
        'version': plan.version,
        'licence': plan.licence,
        # The owner's public name, which is a public identity -- the same
        # amendment §C.4.3 makes to §B.3's no-names rule, and for the same
        # reason. `contributed_by` is a PERSON and is therefore rendered as a
        # handle only, which is already public, never as an email.
        'owner': plan.owner_name,
        'contributed_by': (
            plan.contributed_by.handle if plan.contributed_by_id else None
        ),
        'has_pack': plan.has_pack,
        'pack_sha256': plan.pack_sha256,
        'pack_bytes': plan.pack_bytes,
        'modules': plan.pack_module_count,
        'pages': plan.pack_page_count,
        'media': plan.pack_media_count,
        'published_at': plan.published_at.isoformat() if plan.published_at else None,
    }


@machine_endpoint
def plans(request):
    """GET lists the catalogue; POST is §D's push. One address, two verbs.

    A pushed plan is a new member of this collection, which is what POST to a
    collection means. Giving publication its own verb-shaped address --
    `plans/publish/` -- would put a word that is already a *status* on this
    model into the URL space, where it would then have to be explained every
    time somebody wondered whether hitting it published anything. It does not:
    see `push`.
    """
    if request.method == 'POST':
        return push(request)
    if request.method != 'GET':
        return JsonResponse(
            {'error': 'method_not_allowed'}, status=405,
        )
    return _catalogue(request)


def _catalogue(request):
    """The catalogue, to any authenticated installation.

    NO ENTITLEMENT CHECK, AND THAT IS THE DESIGN RATHER THAN AN OMISSION.
    §B.3 removed `marketplace.browse` from the feature list on purpose:
    "browsing listings is the shop window: it needs the installation credential
    (so the instance can reach the marketplace at all) but not a person's
    entitlement and not a person's link. Gating it would mean asking someone to
    open an account to find out whether they want one."

    So this is the machine-channel half of §C.6's rule -- browse freely, link
    to acquire -- and the gate lives one endpoint along, on the pack.
    """
    try:
        limit = min(int(request.GET.get('limit', DEFAULT_LIMIT)), MAX_LIMIT)
        offset = max(int(request.GET.get('offset', 0)), 0)
    except ValueError:
        return JsonResponse(
            {'error': 'bad_request',
             'detail': 'limit and offset must be integers.'},
            status=400,
        )

    visible = Listing.objects.visible().select_related(
        'owner_account', 'owner_organisation', 'contributed_by',
    )
    total = visible.count()
    return JsonResponse({
        'format': CATALOGUE_FORMAT,
        'total': total,
        'limit': limit,
        'offset': offset,
        'plans': [_plan_json(plan) for plan in visible[offset:offset + limit]],
    })


@require_GET
@machine_endpoint
def plan(request, slug):
    """One listing. A draft is a 404 here exactly as it is on the web."""
    found = get_object_or_404(
        Listing.objects.visible().select_related(
            'owner_account', 'owner_organisation', 'contributed_by',
        ),
        slug=slug,
    )
    return JsonResponse({'format': CATALOGUE_FORMAT, 'plan': _plan_json(found)})


@require_GET
@machine_endpoint
def pack(request, slug):
    """§D's pull. The bytes, to an entitled guardian on this installation.

    THREE CHECKS, AND THEY ARE THREE BECAUSE THEY FAIL FOR DIFFERENT REASONS.

    1. **The subject names somebody linked to THIS installation.** Without it,
       an installation could fetch packs on behalf of any subject whose id it
       learned -- and subject ids travel, in every licence document. A linked
       account is the only thing that makes "who is asking" meaningful on a
       channel that authenticates a machine rather than a person.
    2. **That person's household is entitled.** §D step 2: "the requesting
       guardian's subject must carry `marketplace.download`". Asked of
       `billing` in process, which is the same question and the same row the
       web download asks.
    3. **The listing is published and has a pack.**

    WHY THE SUBJECT IS A PARAMETER AT ALL. This channel authenticates an
    installation, not a person, and §B.3 makes entitlement a property of a
    household -- so a co-op installation holding sixty households cannot have
    one answer. The instance knows which local user asked, and the subject is
    how it says so. That parameter is inside the signature; see `auth.py`,
    where it was not until this endpoint needed it.
    """
    account, problem = _publisher(request)
    if problem:
        return problem

    refusal = entitlement_refusal(account)
    if refusal:
        # 402 rather than 403. The caller is who they say they are and the
        # request is well formed; what is missing is a live subscription, and
        # an instance should render that differently from "you may not" -- one
        # is a thing a family can fix in a minute.
        return JsonResponse(
            {'error': 'not_entitled', 'detail': refusal}, status=402,
        )

    found = get_object_or_404(Listing.objects.visible(), slug=slug)
    if not found.has_pack:
        raise Http404

    # Before the bytes go out, on the same reasoning `catalog.views` gives:
    # a reader who took a copy is a reader who can review it. Returns None for
    # somebody who could publish the listing anyway, which is correct and not
    # an error.
    record_acquisition(found, account)

    response = FileResponse(
        found.pack.open('rb'),
        as_attachment=True,
        filename=f'{found.slug}.coursepack',
    )
    # §D step 3: the instance "verifies the manifest signature and every media
    # hash before touching the database". It can only check what it received
    # against what it was told to expect, and making it spend a second request
    # to learn that is how the two come from different reads.
    response['X-Milepost-Pack-Sha256'] = found.pack_sha256
    response['X-Milepost-Pack-Version'] = found.version
    response['X-Milepost-Licence'] = found.licence
    return response


def _not_yours():
    return JsonResponse(
        {'error': 'unknown_subject',
         'detail': 'That subject is not linked to this installation.'},
        status=403,
    )


def _publisher(request):
    """The account a machine request is acting for, or a refusal.

    Returns `(account, None)` or `(None, response)`. Shared by pull and push
    because the question is identical -- a subject id proves nothing on its own,
    since subject ids travel in every licence document this channel hands out,
    and a link to *this* installation is what makes it mean anything.
    """
    subject = request.GET.get('subject') or request.POST.get('subject')
    if not subject:
        return None, JsonResponse(
            {'error': 'bad_request',
             'detail': 'This names the subject it is acting for.'},
            status=400,
        )
    try:
        account = Account.objects.get(subject=subject)
    except (Account.DoesNotExist, ValidationError, ValueError, TypeError):
        # ValidationError is in that tuple because a UUIDField raises it, not
        # ValueError, when the text is not a UUID -- so `?subject=hello` was a
        # 500 until a test sent one. Unparseable input becoming a server error
        # on a channel anybody with a credential can reach is a free denial of
        # service and a stack trace in a log for the asking.
        #
        # All of them answer as "linked to a different installation" does:
        # both are "not yours to ask for", and telling them apart turns this
        # into a way to test whether a subject id exists.
        return None, _not_yours()

    if not InstallationLink.objects.filter(
        installation=request.installation, account=account,
    ).exists():
        return None, _not_yours()
    return account, None


def push(request):
    """§D's push. An instance publishes a plan it built.

    WHAT IT DOES NOT DO IS PUBLISH. §D's step 4 says the marketplace "stores it
    as a draft listing"; step 5 is "moderation, then published". The status it
    lands in is IN_REVIEW rather than DRAFT, and the difference is who is
    waiting: the author already pressed Publish in their own instance and is
    done, so a DRAFT would be a submission nobody is holding and nothing moves.
    IN_REVIEW is the rung on this model's ladder that means exactly "submitted,
    awaiting moderation", which is the state §D's two steps describe between
    them.

    Nothing here can make it public. `Listing.publish` is the only thing that
    does, it refuses without a recorded acceptance of the publisher terms, and
    the terms are unreviewed drafts -- so publication remains where
    `catalog.views` says it is: blocked on counsel, not on code.

    THE PACK IS RE-VALIDATED WITH THIS PROJECT'S OWN PARSER. §D step 4, and it
    is the reason `catalog.packs` takes bytes rather than a trusted summary:
    "re-validates independently with its own copy of the parser, trusting
    nothing". The manifest names an owner and that name is written by whoever
    built the archive, so it is recorded as `pack_manifest` and believed about
    nothing.

    THE TWO IDENTITY CHECKS ARE §D STEP 4'S OTHER HALF. The subject must be
    linked to this installation, and -- when publishing as an organisation --
    the installation must be bound to that organisation and the account must be
    a member of it. §C.4.3: "a publish is accepted only when both hold", and
    the failures are different, so they are answered differently.
    """
    account, refusal = _publisher(request)
    if refusal:
        return refusal

    # §B.3 lists `marketplace.publish` alongside `marketplace.download`.
    # Publishing costs a subscription, which is also what makes §H.4's
    # PUBLISHED badge cost something.
    not_entitled = entitlement_refusal(account)
    if not_entitled:
        return JsonResponse(
            {'error': 'not_entitled', 'detail': not_entitled}, status=402,
        )

    upload = request.FILES.get('pack')
    if upload is None:
        return JsonResponse(
            {'error': 'bad_request', 'detail': 'A push carries a pack.'},
            status=400,
        )

    fields, problem = _plan_fields(request)
    if problem:
        return problem

    owner_account, owner_organisation, problem = _owner(request, account)
    if problem:
        return problem

    listing = Listing(
        slug=unique_slug(fields['title']),
        owner_account=owner_account,
        owner_organisation=owner_organisation,
        contributed_by=account,
        status=Listing.Status.IN_REVIEW,
        **fields,
    )
    try:
        # Validated before anything is written, so a refused pack leaves
        # nothing behind -- including no listing. `attach` saves; this is the
        # only place the row is created.
        attach(listing, upload.read())
    except ValidationError as refused:
        return JsonResponse(
            {'error': 'bad_pack',
             'detail': '; '.join(refused.messages)},
            status=400,
        )

    return JsonResponse(
        {'format': CATALOGUE_FORMAT, 'plan': _plan_json(listing),
         'status': listing.status},
        status=201,
    )


def _plan_fields(request):
    """The listing's own fields, validated. `(fields, None)` or `(None, response)`.

    `subject_area` rather than `subject`, and the rename is worth explaining
    because it looks like gratuitous divergence from the model. On this channel
    `subject` already means §B.3's opaque marketplace subject id -- it is that
    in the licence payload and in pull's query string -- and a word that means
    an opaque person id in one field and "science" in the next is a bug waiting
    for somebody to be tired. One meaning per name, and the curriculum field is
    the one that moved because it is the one with an alternative.
    """
    title = (request.POST.get('title') or '').strip()
    summary = (request.POST.get('summary') or '').strip()
    area = request.POST.get('subject_area')

    if not title or not summary:
        return None, JsonResponse(
            {'error': 'bad_request',
             'detail': 'A plan needs a title and a summary.'}, status=400,
        )
    if slug_for(title) in RESERVED_SLUGS:
        return None, JsonResponse(
            {'error': 'bad_request', 'detail': 'That title is reserved.'},
            status=400,
        )
    if area not in Subject.values:
        return None, JsonResponse(
            {'error': 'bad_request',
             'detail': f'subject_area must be one of: {", ".join(Subject.values)}.'},
            status=400,
        )

    try:
        low = int(request.POST.get('grade_min', GRADE_MIN))
        high = int(request.POST.get('grade_max', GRADE_MAX))
    except ValueError:
        return None, JsonResponse(
            {'error': 'bad_request', 'detail': 'Grades are integers.'},
            status=400,
        )
    if not (GRADE_MIN <= low <= GRADE_MAX and GRADE_MIN <= high <= GRADE_MAX):
        return None, JsonResponse(
            {'error': 'bad_request',
             'detail': f'Grades run from {GRADE_MIN} to {GRADE_MAX}.'},
            status=400,
        )
    if low > high:
        # Checked here as well as by the database constraint, for the reason
        # `PlanForm.clean` gives: the constraint is what makes it true, this is
        # what makes it a sentence rather than an IntegrityError.
        return None, JsonResponse(
            {'error': 'bad_request',
             'detail': 'The lowest grade cannot be above the highest.'},
            status=400,
        )

    return {
        'title': title[:150],
        'summary': summary[:300],
        'description': (request.POST.get('description') or '').strip(),
        'subject': area,
        'grade_min': low,
        'grade_max': high,
    }, None


def _owner(request, account):
    """Who holds the listing. `(account, organisation, None)` or `(.., response)`.

    §C.4.2's three references, decided here: exactly one owner, plus
    `contributed_by`, which the caller sets to the publishing account whichever
    owner applies.
    """
    publish_as = request.POST.get('publish_as')
    if not publish_as:
        return account, None, None

    organisation = request.installation.organisation
    if organisation is None or organisation.slug != publish_as:
        # §C.4.3's installation layer. The installation names the ONLY
        # organisation it may publish as, and a mismatch is a misconfigured
        # deployment rather than a permissions problem -- which is why it does
        # not say the same thing as the member check below.
        return None, None, JsonResponse(
            {'error': 'not_bound',
             'detail': 'This installation is not bound to that organisation.'},
            status=403,
        )
    if not organisation.is_active:
        return None, None, JsonResponse(
            {'error': 'organisation_closed',
             'detail': 'That organisation is closed and cannot publish.'},
            status=403,
        )
    if not organisation.can_publish(account):
        # §C.4.3's person layer. A non-member publishing from a bound
        # installation is a permissions error, and stays a separate answer.
        return None, None, JsonResponse(
            {'error': 'not_a_member',
             'detail': 'That account is not a member of that organisation.'},
            status=403,
        )
    return None, organisation, None
