"""Signing up, and one person's public page.

Signing in and out are Django's own views, wired up in urls.py. They are
correct, they are maintained, and a hand-written login form is a place to get
session fixation or timing wrong for no gain.
"""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

# THE ONE-WAY RULE BENDS FOR A VIEW AND NEVER FOR A MODEL. `catalog` imports
# `accounts` because a listing needs an owner; `accounts` importing `catalog`
# back would ordinarily be the start of a cycle. It is safe in exactly this
# direction and exactly here: a view runs long after both app registries are
# loaded, so nothing is half-built when this executes, and `profile` is the
# template rendering the facts rather than a model depending on them. The
# reverse -- a `catalog` model importing an `accounts` view -- would be the
# real cycle, and nothing does it.
#
# The alternative was a lazy import inside `profile`. That hides the
# dependency from anybody reading the file's imports to find out what this app
# touches, which is the thing the rule is protecting.
from catalog.reputation import facts_for

from .forms import ProfileForm, SignUpForm
from .models import Account, awards_for


def sign_up(request):
    """Create an account and sign in with it.

    Signed straight in afterwards rather than bounced to the login page: the
    person has just proved they know the password by choosing it, and making
    them type it again is friction that buys nothing.
    """
    if request.user.is_authenticated:
        return redirect('profile', handle=request.user.handle)

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        account = form.save()
        login(request, account)
        return redirect('profile', handle=account.handle)

    return render(request, 'accounts/sign_up.html', {'form': form})


def profile(request, handle):
    """One person, as everybody else sees them.

    PUBLIC, AND THEREFORE SHOWS ONLY WHAT SOMEBODY CHOSE TO PUBLISH. The
    email is not here and must never be: it is a credential, and it is the
    field this model keeps separate from `handle` for exactly this reason.

    Inactive accounts are a 404 rather than a page saying somebody was here.
    Whether a given handle belongs to a deactivated account is not something
    a stranger is owed, and answering it turns this into a way to enumerate
    who has ever signed up. Accounts that are not public -- staff, made by
    `createsuperuser` -- are a 404 for the same reason and a second one: an
    operator signed up for a login, not for a page announcing them as a
    member.

    REPUTATION IS HERE NOW, and it is the derived half only. §H.2 splits it
    into facts that are counted and badges that are granted; `reputation.py`
    is the first and stores nothing, so this page gained four numbers and no
    new table. Badges are a model and a later step.

    The facts are computed even for a person with nothing published -- four
    cheap counts -- and the template renders none of it when `published` is
    zero. Deciding that here instead would put "what is worth showing" in two
    places, and the template is the one that knows what a row looks like.
    """
    person = get_object_or_404(
        Account, handle=handle.lower(), is_active=True, is_public=True,
    )
    return render(request, 'accounts/profile.html', {
        'person': person,
        'is_own': request.user.is_authenticated and request.user.pk == person.pk,
        # Reached through the reverse accessor rather than by importing
        # `catalog`, which keeps the dependency running one way: catalog
        # knows about accounts because a listing needs an owner, and accounts
        # does not need to know what a listing is to show a list of them.
        # `visible()` is the one place that decides what a stranger sees, so
        # drafts stay out of this without this page having an opinion.
        'plans': person.listings.visible(),
        # Four queries on a page that already runs one. Not cached, and
        # `reputation.facts_for` argues why: a stored reputation number is a
        # number that can be wrong, and these exist to be checkable against
        # rows anybody can see.
        'facts': facts_for(person),
        # §H.3's badges -- the granted half, beside the counted one. Both
        # render nothing when there is nothing, so a new account's page is
        # still just a name.
        'awards': awards_for(person),
    })


@login_required
def edit_profile(request):
    """Change how you appear. Not who you are -- see ProfileForm.

    Saving lands on your public page, which is the confirmation: the new name
    is there, in the place other people read it. An account with no public
    page -- staff -- would land on a 404 instead, so it comes back here with
    the saved value in the field.
    """
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if not request.user.is_public:
            return redirect('edit_profile')
        return redirect('profile', handle=request.user.handle)

    return render(request, 'accounts/edit_profile.html', {'form': form})
