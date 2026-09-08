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
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PlanForm
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
