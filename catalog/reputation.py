"""The four derived facts, which are queries rather than columns.

§H.2 splits reputation in two and says keeping them apart is most of the
design:

    DERIVED FACTS   counts over rows that already exist. Never stored, never a
                    column, recomputed on read. No new model at all.
    AWARDED BADGES  discrete grants, each with a reason and a date, each
                    revocable. One new model.

"Nothing is stored that could be counted. A derived fact is a query; a badge is
a decision. The line between them is whether a human or a rule had to judge
something."

This module is the first half. It stores nothing.

IN `catalog` RATHER THAN `accounts`, WHICH IS WHERE §H.3 PUTS THE BADGE MODEL.
Both are about the same two subjects, so the instinct is to keep them together
-- but every row counted here is a `catalog` row, and `accounts` is imported BY
this app rather than the other way round. Reputation living in `accounts` would
mean either a circular import or a lazy one inside every function, to buy
nothing but adjacency. The `Award` model still belongs there when it lands:
it is a fact about a subject, not about a listing.

WHAT IS DELIBERATELY NOT COUNTED
=================================
Anything measuring what somebody CONSUMED -- plans downloaded, reviews written,
days active. §H.2: those "measure a subscriber spending a subscription they
already paid for, which is not a contribution and should not read as one. It is
also the one number a single paying account can inflate on its own."

THE COUNT ALWAYS TRAVELS WITH THE AVERAGE
=========================================
`Listing.average_rating` set this rule and argued it first: the number is real
from the first review, and the count is what makes it readable. Four-point-five
from two reviews and four-point-five from two hundred are different claims.
`ratings` below returns both or neither, so a template cannot render one alone
by forgetting.
"""

from django.db.models import Avg, Count

from .models import Acquisition, Listing, Review


def owned_listings(subject):
    """The published listings this subject owns, as a queryset.

    ONE PLACE DECIDES WHAT "OWNED BY" MEANS, because `Listing` splits ownership
    across two nullable columns and a `CheckConstraint` guarantees exactly one
    is set. A caller filtering on the wrong one gets an empty page rather than
    an error, which is the worst way for this to be wrong.

    `visible()` rather than a status filter written again here: that method is
    documented as "the one place that decides" what a stranger may see, and a
    draft listing must not count toward anybody's reputation -- it would let
    somebody's numbers move without anything being shared.
    """
    listings = Listing.objects.visible()
    if _is_organisation(subject):
        return listings.filter(owner_organisation=subject)
    return listings.filter(owner_account=subject)


def _is_organisation(subject):
    """Duck-typed on the field `Listing` would store it in.

    An `isinstance` check would mean importing `Organisation` here to compare
    against, and the question being asked is genuinely "which column does this
    go in" rather than "what class is this".
    """
    return hasattr(subject, 'slug')


def households_served(subject):
    """How many distinct households have taken a copy of anything they own.

    HOUSEHOLDS, NOT ACCOUNTS, AND §H.2's CAVEAT ON THIS IS NOW SPENT. That
    section says to render this as "downloaded N times" rather than "used by N
    families" *until households are countable*, because a distinct-account
    count is an upper bound -- two linked parents read as two families -- and
    an overstatement in the publisher's favour is the wrong direction for the
    one number a browsing parent uses to judge a plan.

    `billing` landed in revision 25 and `Acquisition.household` landed with it,
    so the honest number is now available and this counts it. The caveat
    described a real constraint that no longer holds; the caution it expressed
    is satisfied rather than abandoned.

    A row whose household is null cannot happen -- the column is not nullable
    -- but `distinct()` on a join is counted explicitly rather than through
    `Count(distinct=True)` in an annotation, because the latter silently
    becomes per-listing when combined with the others.
    """
    return (
        Acquisition.objects
        .filter(listing__in=owned_listings(subject))
        .values('household')
        .distinct()
        .count()
    )


def ratings(subject):
    """`(count, average)` over every review of anything they own.

    BOTH OR NEITHER. An average with no count beside it is the failure
    `Listing.average_rating` exists to prevent one level down, and returning
    them as a pair is what stops a template rendering one alone.

    `average` is None when there are no reviews -- not zero. Zero is a rating
    somebody could in principle give; None is the absence of any, and a page
    that shows "0.0 out of 5" for a plan nobody has reviewed has invented a
    verdict.
    """
    summary = (
        Review.objects
        .filter(listing__in=owned_listings(subject))
        .aggregate(count=Count('id'), average=Avg('rating'))
    )
    return summary['count'] or 0, summary['average']


def contributed_count(account):
    """Published listings this PERSON pressed Publish on, whoever owns them.

    NOT A DUPLICATE OF `owned_listings`, and §C.4.2 split ownership from the
    historical fact of who did the work precisely so both could be rendered:
    "Published by Oak Hill Co-op, contributed by Priya". A co-op's plans belong
    to the co-op forever; the work was still somebody's.

    Takes an account rather than a subject because an organisation cannot press
    anything. Asking it of one is a question with no meaning, so it is not
    offered.
    """
    return Listing.objects.visible().filter(contributed_by=account).count()


def facts_for(subject):
    """Everything §H.2 lists, for one subject, as a dict a template renders.

    FOUR QUERIES AND NO CACHING. Each is a count over an indexed foreign key on
    a table that will be small for a long time, and a cached reputation number
    is a number that can be wrong -- which is worse here than slow, because the
    whole point of these is that they are checkable against the rows anybody
    can see.

    `contributed` is absent for an organisation rather than zero. Zero would
    read as "this co-op has contributed nothing", which is not what the absence
    of a meaningless question means.
    """
    count, average = ratings(subject)
    facts = {
        'published': owned_listings(subject).count(),
        'households': households_served(subject),
        'reviews': count,
        'average_rating': average,
    }
    if not _is_organisation(subject):
        facts['contributed'] = contributed_count(subject)
    return facts
