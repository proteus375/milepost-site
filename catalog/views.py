"""Browsing plans, and writing one down.

THERE IS NO PUBLISH BUTTON HERE, AND THAT IS NOT AN OVERSIGHT
---------------------------------------------------------------
`Listing.publish` refuses without a recorded acceptance of the publisher
terms, which is §4.4.4 working as designed: both the contributor and, for an
organisation, the organisation itself must warrant they had the right to share
what they publish, and a warranty nobody recorded accepting is not a warranty.

Accepting terms means showing them. `legal/README.md` is unambiguous about
what that would mean today: "None of this has been reviewed by a lawyer.
Nothing here should be published, linked from the site, or relied on until it
has been." So the page that would collect an acceptance cannot be built yet,
and building a publish button that always refuses would be worse than not
having one.

What blocks publishing is counsel, not code. The recording mechanism is built
and tested; the admin can move a listing to PUBLISHED in the meantime, which
is the operator path §A asks for anyway.

WHY BROWSING EXISTS BEFORE ANYTHING IS IN IT
---------------------------------------------
Same reason the profile page was built before there was anything to put on it:
the surface a thing hangs from should exist before the thing does, or the
commit that adds the thing has to invent its home under time pressure.
"""

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from billing.models import entitlement_refusal

from .forms import PackForm, PlanForm, ReviewForm
from .models import (
    Listing, Review, Subject, acquisition_for, may_review, record_acquisition,
)


def plans(request):
    """Every published plan, newest first, optionally by subject."""
    listings = Listing.objects.visible().select_related(
        'owner_account', 'owner_organisation',
    )
    subject = request.GET.get('subject') or ''
    if subject in Subject.values:
        listings = listings.filter(subject=subject)

    return render(request, 'catalog/plans.html', {
        'listings': listings,
        'subjects': Subject.choices,
        'chosen': subject,
    })


def listing(request, slug):
    """One plan.

    A draft nobody may read is a 404 rather than a 403, on the reasoning
    already written in `accounts.views.profile`: whether a given address
    belongs to anything is not something a stranger is owed, and answering it
    turns the address bar into a way to enumerate what exists.
    """
    plan = get_object_or_404(
        Listing.objects.select_related('owner_account', 'owner_organisation',
                                       'contributed_by'),
        slug=slug,
    )
    if not plan.may_be_read_by(request.user):
        raise Http404

    reviews = plan.reviews.select_related('account')
    mine = None
    if getattr(request.user, 'is_authenticated', False):
        mine = reviews.filter(account=request.user).first()

    # Once, not twice. `may_review` was two calls when it was one query; it
    # now looks up an acquisition and the household's other reviews, and
    # asking the same question twice per page view is three queries nobody
    # needs.
    no_review_because = may_review(plan, request.user)
    # Reaching a draft at all means being allowed to -- anybody else was
    # refused above -- so on a draft, the reader is the editor.
    can_edit = not plan.is_published

    return render(request, 'catalog/listing.html', {
        'plan': plan,
        'reviews': reviews.exclude(pk=mine.pk) if mine else reviews,
        'my_review': mine,
        # A sentence when they may not review, or None when they may. The
        # page says which -- "you cannot review a plan you publish" and "this
        # needs a copy of the pack first" are different situations and a
        # missing form explains neither.
        'no_review_because': no_review_because,
        'review_form': ReviewForm(instance=mine) if not no_review_because else None,
        'pack_form': PackForm() if not plan.is_published else None,
        'can_edit': can_edit,
        # The same shape, for the same reason. A missing download button
        # explained nothing while nobody could download; now that the answer
        # depends on the reader, "not on a household" and "lapsed" are
        # different situations and only one of them is a thing to go and fix.
        'no_download_because': None if can_edit else entitlement_refusal(request.user),
    })


@login_required
def your_plans(request):
    """Everything you can edit, published or not.

    THIS PAGE IS WHY DRAFTS ARE NOT LOST. Without it a draft has no address
    anybody can find: the catalogue shows published plans, a profile shows
    published plans, and somebody who starts a plan and closes the tab has
    written something the site will never offer them again. It was found by
    having to read the database to answer "where did that plan go".

    Organisation plans are here too, for everybody who may publish them.
    That is the point of an organisation owning a listing -- a co-op's draft
    is not the private property of whoever opened the form.
    """
    listings = Listing.objects.filter(
        models.Q(owner_account=request.user)
        | models.Q(owner_organisation__memberships__account=request.user)
    ).distinct().select_related('owner_account', 'owner_organisation')

    return render(request, 'catalog/your_plans.html', {'listings': listings})


@login_required
def new_plan(request):
    form = PlanForm(request.POST or None, account=request.user)
    if request.method == 'POST' and form.is_valid():
        return redirect(form.save())

    return render(request, 'catalog/plan_form.html', {
        'form': form, 'is_new': True,
    })


@login_required
def edit_plan(request, slug):
    plan = get_object_or_404(Listing, slug=slug)
    if not plan.may_be_read_by(request.user) or plan.is_published:
        # A published listing is not editable in place. What people
        # downloaded is what the manifest said it was, and quietly changing
        # the thing behind a version somebody already has is the failure
        # `version` exists to prevent. A revision is a new version, which
        # arrives with the pack.
        raise Http404

    form = PlanForm(request.POST or None, instance=plan, account=request.user)
    if request.method == 'POST' and form.is_valid():
        return redirect(form.save())

    return render(request, 'catalog/plan_form.html', {
        'form': form, 'plan': plan, 'is_new': False,
    })


@login_required
def upload_pack(request, slug):
    """Attach a course pack to a draft.

    A DRAFT ONLY, and for the same reason a published listing is not editable
    in place: what people downloaded is what the manifest said it was, and
    swapping the archive behind a version somebody already holds is exactly
    the failure `version` exists to prevent. A revision is a new version.

    The listing is resolved before the form is touched, so somebody without
    edit rights gets a 404 rather than an upload that is parsed and then
    refused -- there is no reason to run a stranger's archive through the
    reader to find out they were not allowed to send it.
    """
    plan = get_object_or_404(Listing, slug=slug)
    if not plan.may_be_read_by(request.user) or plan.is_published:
        raise Http404

    form = PackForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        return redirect(form.attach_to(plan))

    return render(request, 'catalog/listing.html', {
        'plan': plan, 'pack_form': form, 'can_edit': True,
    })


@login_required
def download_pack(request, slug):
    """The pack itself, to somebody entitled to it.

    THE GATE THIS VIEW WAITED FOR NOW EXISTS. Until `billing` there was no
    way to tell an entitled reader from any other signed-in one, so this
    served a pack only to the people who could already replace it. It now
    asks `billing` the one question that app exists to answer, in process.

    NOT §B.3'S TOKEN, and the distinction is worth keeping straight. That
    token exists so an installation in the field can verify entitlement
    offline, with a grace window for the case where the marketplace cannot be
    reached. Nothing about that applies to a browser talking to the
    marketplace itself: if this code is running, the marketplace was reached,
    so there is no staleness to grace and no signature to check. The token
    arrives with `instances`, reading the same rows this reads.

    A REFUSAL HERE IS A 403 WITH THE REASON, NOT A 404, which reverses what
    this view did before and matches `review_plan`. The 404 was right while
    the answer was "nobody may have this yet" -- there was nothing to explain
    and no action to offer. The answer is now "you may not have this, and
    here is what would change that", and hiding that behind a 404 tells a
    paying customer whose subscription lapsed that the page is gone.

    The listing's existence is not the secret; a published plan is on a page
    they are looking at. An unpublished one still 404s, because whether an
    address belongs to anything is not something a stranger is owed.

    Streamed by a view rather than served from a URL prefix, which is why
    settings define MEDIA_ROOT and no MEDIA_URL: a guessable path would be
    this check bypassed by typing an address.
    """
    plan = get_object_or_404(Listing, slug=slug)
    if not plan.has_pack or not plan.may_be_read_by(request.user):
        raise Http404

    # Order matters. Somebody who could edit this listing is holding their own
    # work, which needs no entitlement and records no acquisition -- asking
    # them for a subscription to read what they wrote would be absurd, and
    # `record_acquisition` refuses to record it anyway.
    if not plan.may_be_edited_by(request.user):
        refusal = entitlement_refusal(request.user)
        if refusal:
            return HttpResponseForbidden(refusal)

    # Noted before the bytes go out, so a reader who took a copy is a reader
    # who can review it. Refused for anybody who could publish the listing --
    # an author holding their own work is not an acquisition.
    record_acquisition(plan, request.user)

    return FileResponse(
        plan.pack.open('rb'),
        as_attachment=True,
        filename=f'{plan.slug}.coursepack',
    )



@login_required
def review_plan(request, slug):
    """Write or change your review of a plan.

    One view for both, because they are the same act: `may_review` already
    decided whether this person is entitled to have an opinion on the record,
    and whether they have said it before changes only which row is saved.

    A refusal is a 403 with the reason, not a 404. Unlike a draft, the
    existence of a published listing is not a secret -- the reader is looking
    at it. What they are being told is that this particular person may not
    review this particular plan, and every one of those reasons is something
    they should hear: you publish this, you have not got a copy, you are not
    signed in.
    """
    plan = get_object_or_404(Listing, slug=slug)

    refusal = may_review(plan, request.user)
    if refusal:
        return HttpResponseForbidden(refusal)

    existing = Review.objects.filter(listing=plan, account=request.user).first()
    form = ReviewForm(request.POST or None, instance=existing)

    if request.method == 'POST' and form.is_valid():
        review = form.save(commit=False)
        review.listing = plan
        review.account = request.user
        # From the acquisition rather than from the person's household today,
        # for the reason on the field: the opinion belongs to the household
        # that took the copy. `may_review` has already established that this
        # row exists.
        # Stamped only when it is written, so an edit does not silently
        # re-point an old opinion at a pack the author never saw.
        if not existing:
            review.household = acquisition_for(plan, request.user).household
            review.version_reviewed = plan.version
        review.save()
        return redirect(plan)

    return render(request, 'catalog/review_form.html', {
        'plan': plan, 'form': form, 'is_new': existing is None,
    })
