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
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PackForm, PlanForm
from .models import Listing, Subject


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

    return render(request, 'catalog/listing.html', {
        'plan': plan,
        'pack_form': PackForm() if not plan.is_published else None,
        # Reaching a draft at all means being allowed to -- anybody else was
        # refused above -- so on a draft, the reader is the editor.
        'can_edit': not plan.is_published,
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

    TODAY THAT MEANS ITS OWNER AND NOBODY ELSE, and the gap is deliberate
    rather than forgotten. §B.3 checks a download per household against a
    fresh token carrying `marketplace.download`; there is no billing app, so
    there are no tokens, so there is no way to tell an entitled reader from
    any other signed-in one. Serving published packs to whoever asks would
    not be an unfinished feature, it would be giving away other people's
    work -- so this serves a pack to the people who could already replace it,
    and waits.

    Streamed by a view rather than served from a URL prefix, which is why
    settings define MEDIA_ROOT and no MEDIA_URL: a guessable path would be
    this check bypassed by typing an address.
    """
    plan = get_object_or_404(Listing, slug=slug)
    if not plan.has_pack or not plan.may_be_read_by(request.user):
        raise Http404
    if plan.is_published and not _may_edit(plan, request.user):
        raise Http404

    return FileResponse(
        plan.pack.open('rb'),
        as_attachment=True,
        filename=f'{plan.slug}.coursepack',
    )


def _may_edit(plan, user):
    """Whoever could change the listing. Not a permission of its own.

    A published listing is readable by everybody, so `may_be_read_by` stops
    answering the question "is this yours" the moment it goes live.
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    if plan.owner_account_id:
        return plan.owner_account_id == user.pk
    return plan.owner_organisation.can_publish(user)
