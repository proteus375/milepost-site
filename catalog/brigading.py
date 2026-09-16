"""What a brigade looks like in the data, as a query a person reads.

§H.7 is unusually specific about what NOT to build, and this module is shaped
by the refusal more than by the detection:

    So: build the query, not the detector. A staff view over that shape, in the
    Django admin, which §A already names as one of the two reasons the stack
    was chosen at all. Not an automatic threshold that suppresses reviews.

Three reasons are given, and each one is a constraint on this file:

  * The volume is small enough for a person to look, and will be for a long
    time. So this returns rows for a human to read, not a verdict.
  * The false positive is a genuinely popular new listing that forty families
    acquire and rate in a week -- "which is the *best* thing that can happen on
    this platform, and an automatic rule would mistake it for the worst". So
    the thresholds below are tuned to let that through, and there is a test
    named for it.
  * A suppression rule is invisible to the person it acts on and produces a
    support conversation nobody in it can win. So **nothing here writes
    anything**. No review is hidden, no rating is discounted, no account is
    flagged on any record. This module only reads.

NOTHING WAS ADDED TO THE SCHEMA TO MAKE THIS POSSIBLE, and §H.7 says why:
`Acquisition.acquired_at` and `Review.created_at` are both recorded, so "the
signature is a cluster of first-time acquisitions of one listing inside a short
window, followed by low ratings, from accounts with little other history.
Nothing needs to be added to see it."

THE §F.4 LESSON, APPLIED BEFORE THE FACT
=========================================
The §E.7 audit found that the untested direction is the one that fails, and the
untested direction of an anti-brigading rule is a legitimate surge. §H.7 asks
for the reverse test in the same breath as the feature: "whatever query ships
must be run against a synthetic popular launch and produce nothing." It is
written, it is named for what it protects, and it is the test that should be
read first by anybody changing a number in this file.
"""

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Acquisition, Listing, Review

#: How far back a cluster is looked for. A brigade is a thing that happens in
#: days; a fortnight is long enough to catch one that started slowly and short
#: enough that an ordinary trickle of reviews never fills it.
WINDOW = timedelta(days=14)

#: Fewer reviews than this in the window is not a cluster, it is a Tuesday.
#: Set where it is because a handful of unhappy readers is the normal texture
#: of a catalogue and a queue that surfaces it is a queue nobody reads.
CLUSTER_MINIMUM = 5

#: A rating at or below this is the "low ratings" half of the signature.
#: `Rating.FAIR` is "Some of it worked" -- a real opinion somebody might hold
#: about a plan they paid for, which is exactly why two and not three: three is
#: "Worth using", and a cluster of those is a mild plan, not an attack.
POOR = Review.Rating.FAIR

#: What share of the cluster has to be poor before it is worth a person's
#: attention. Not all of it: a brigade that happens to land on the same week as
#: two genuine enthusiasts should not disappear because the average moved.
MOSTLY_POOR = 0.75

# EVERY NUMBER ABOVE IS A QUEUE THRESHOLD, NOT A SUPPRESSION THRESHOLD, and the
# difference is what makes them safe to be wrong about. Set them too low and a
# staff member spends thirty seconds dismissing a listing that was merely
# disliked. Set them too low in a rule that hid reviews and you would have
# silently deleted somebody's honest opinion of a plan they paid for. §H.10's
# warning about `WIDELY_USED` -- that a badge granted at the wrong bar has to be
# taken from people who did nothing -- is the same asymmetry seen from the other
# side, and it is the reason this was built as a list rather than a rule.


def clusters(*, as_of=None, window=WINDOW):
    """Listings taking a concentrated run of low ratings. Read-only.

    Returns a list of dicts, worst first, each carrying enough for somebody to
    decide in a few seconds: the listing, how many reviews landed in the
    window, how many of those were poor, the window's average, and how many of
    the reviewing households have no other acquisition at all.

    A ROLLING WINDOW ENDING AT `as_of`, WHICH ANSWERS "WHAT IS HAPPENING NOW".
    A historical sweep for brigades that happened last quarter is a different
    tool with a different shape, and inventing it now would mean guessing at
    how somebody would want to page through it.

    `newcomers` IS REPORTED AND IS NOT A FILTER, and that is deliberate.
    §H.7's signature mentions "accounts with little other history", and a
    coordinated group of real subscribers with a grievance -- which §H.7 says
    "costs nothing extra at all" -- has plenty of history. Filtering on newness
    would hide exactly the brigade the design says is cheapest to mount. So the
    number is shown and a person weighs it.
    """
    as_of = as_of or timezone.now()
    since = as_of - window

    in_window = Review.objects.filter(created_at__gte=since, created_at__lte=as_of)
    candidates = (
        in_window
        .values('listing')
        .annotate(
            reviews=Count('id'),
            poor=Count('id', filter=Q(rating__lte=POOR)),
            average=Avg('rating'),
        )
        .filter(reviews__gte=CLUSTER_MINIMUM)
    )

    found = []
    for row in candidates:
        # THE LINE THE POPULAR LAUNCH WALKS THROUGH. Forty families acquiring
        # and rating a good plan in a week produces a big `reviews` and a
        # `poor` of nearly nothing, so it never reaches the list.
        if row['poor'] < row['reviews'] * MOSTLY_POOR:
            continue

        households = list(
            in_window.filter(listing_id=row['listing'])
            .values_list('household', flat=True)
        )
        newcomers = (
            Acquisition.objects
            .filter(household__in=households)
            .values('household')
            .annotate(acquisitions=Count('id'))
            .filter(acquisitions=1)
            .count()
        )

        found.append({
            'listing': Listing.objects.get(pk=row['listing']),
            'reviews': row['reviews'],
            'poor': row['poor'],
            'average': row['average'],
            'households': len(set(households)),
            'newcomers': newcomers,
            'since': since,
            'until': as_of,
        })

    # Worst first: the most low ratings, then the lowest average. Somebody
    # opening this page should not have to sort it.
    found.sort(key=lambda cluster: (-cluster['poor'], cluster['average']))
    return found
