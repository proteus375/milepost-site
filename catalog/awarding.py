"""Which subject earns which badge, and when.

THE POLICY ABOVE `accounts.grant`, WHICH IS ONLY THE MECHANISM. §H.9 asks for
"one idempotent function per badge kind, run on the events that can change the
answer -- a publish, an acquisition, a review -- plus a periodic pass for
`SUSTAINED`, which is the only one that turns true with no event behind it."
This module is those functions, and `run` is that pass.

IN `catalog` THOUGH `Award` LIVES IN `accounts`, for the reason
`catalog.reputation` gives one file over: every row these rules read is a
`catalog` row, and `accounts` is imported BY this app rather than the other way
round. A rule module in `accounts` would need a lazy import inside every
function to buy nothing but adjacency.

ONLY TWO OF THE FIVE KINDS ARE HERE, AND THAT IS §H.10's ORDERING RATHER THAN
AN OMISSION
============================================================================
`PUBLISHED` and `SUSTAINED` are the two that need no threshold, "so they ship
before N and M have to be guessed". `WIDELY_USED` and `WELL_REVIEWED` are step
5 and must not jump the queue: §H.10 is unambiguous that a threshold badge
granted at the wrong bar "has to be revoked from people who did nothing, which
is the most expensive small mistake available here", and the bar comes from the
first hundred real listings rather than from an afternoon's guess. `FOUNDING`
has no rule at all by design -- it is staff judgement, granted in the admin.

EVERY RULE IS IDEMPOTENT AND NONE OF THEM REVOKE
=================================================
A rule may grant. Taking a badge away is a decision a person makes, with a
reason, through `Award.revoke` -- which is why `grant` returns a revoked award
rather than issuing a fresh one. A pass that silently un-revoked would undo a
moderator's judgement every time it ran, and it runs on a timer.
"""

from datetime import timedelta

from django.utils import timezone

from accounts.models import Award, grant

from .models import Listing

#: §H.4: "a published listing is still live and unwithdrawn at twelve months".
#: 365 days rather than `relativedelta(years=1)`, because the badge is about
#: having lasted rather than about an anniversary, and nothing here should
#: depend on which side of a leap day a plan was published.
SUSTAINED_AFTER = timedelta(days=365)


def award_published(listing):
    """`PUBLISHED`, for a listing that has gone live. Idempotent.

    GRANTED TO BOTH THE CONTRIBUTOR AND THE OWNER, AND THE DESIGN IS NOT
    UNANIMOUS ABOUT THAT -- so it is decided here, in the open, rather than
    picked quietly.

      * §H.4's badge table names the subject as "contributor, **and owner**".
      * §H.5's split table says `PUBLISHED` goes to "the contributor, always a
        person", because `contributed_by` is the historical fact of who did
        the work.

    Read strictly, the second would leave a co-op with no badge at all: every
    other kind it can hold is a threshold badge, and thresholds are step 5. A
    co-op that has published four plans would show an empty page for months,
    which reads as "this co-op has done nothing" -- the precise misreading §C.4
    exists to prevent.

    §H.5's own prose is the tie-breaker: "a co-op's work accrues to the co-op,
    **and** the person who did it keeps visible credit for having done it."
    Both, then. Its table is answering which AXIS each badge hangs on -- plan
    facts to the owner, work facts to the contributor -- and `PUBLISHED` is the
    one badge that is legibly about both.

    Reversing this is three lines and one test if the reading is wrong.

    ONE BADGE, NOT TWO, FOR A PERSONAL LISTING. The contributor and the owner
    are the same account, and `grant` is idempotent, so the second call finds
    the first row. That falls out of the unique constraint rather than being
    checked here, which is the way round it should be.
    """
    if not listing.is_published:
        return []

    granted = []
    # The contributor first: on a personal listing the two are the same
    # account, and this way the reason recorded is the one about the person.
    if listing.contributed_by_id:
        granted.append(grant(
            listing.contributed_by, Award.Kind.PUBLISHED,
            reason=f'Published {listing.title}.',
        ))
    owner = listing.owner
    if owner is not None and owner != listing.contributed_by:
        granted.append(grant(
            owner, Award.Kind.PUBLISHED,
            reason=f'Published {listing.title}.',
        ))
    return granted


def award_sustained(listing, *, as_of=None):
    """`SUSTAINED`, for a plan still live twelve months on. Idempotent.

    TO THE OWNER AND HUNG OFF THE LISTING, because §H.5 is unambiguous about
    this one: it is a fact about the plan, and the plan belongs to whoever owns
    it. A contributor who has since left the co-op does not take it with them,
    for the same reason they do not take the plan.

    WHAT FAKING IT COSTS IS TIME, which §H.4 calls "the one input that cannot
    be bought" -- and that is the whole reason this badge is admissible without
    a threshold to argue about.

    A LISTING PUBLISHED WITH NO `published_at` IS SKIPPED RATHER THAN GUESSED.
    `publish` always sets it, but an operator moving a listing to PUBLISHED
    from the admin can leave it null -- and that is the ordinary path today,
    since `Listing.publish` refuses without a recorded acceptance of terms
    nobody may show yet. There is no honest date to substitute: `created_at` is
    when somebody started writing, which can be a year before anybody saw it.
    The admin can set the real date, and then the next pass grants.
    """
    if not listing.is_published or listing.published_at is None:
        return None
    if (as_of or timezone.now()) - listing.published_at < SUSTAINED_AFTER:
        return None
    owner = listing.owner
    if owner is None:
        return None
    return grant(
        owner, Award.Kind.SUSTAINED, listing=listing,
        reason=f'{listing.title} has been published for a year.',
    )


def run(*, as_of=None):
    """Apply every rule to every published listing. Returns what it granted.

    THE PERIODIC PASS §H.9 ASKS FOR, AND ALSO THE REPAIR. `SUSTAINED` turns
    true with no event behind it, so it needs this. `PUBLISHED` has an event --
    `Listing.publish` calls its rule directly -- and still needs this, for two
    reasons worth writing down:

      * The admin is the ordinary publishing path today. `ListingAdmin` can
        move a listing to PUBLISHED without going through `publish`, because
        `publish` refuses without a terms acceptance and the terms cannot be
        shown until counsel has read them. A rule wired only to the method
        would grant nothing for as long as that holds.
      * A rule that failed to fire is otherwise a Saturday problem. This makes
        it a command somebody can run.

    IDEMPOTENT THROUGHOUT, so it is safe on a timer and safe twice by hand.
    Nothing here revokes.

    RETURNS `granted` AND `new` SEPARATELY, because they answer different
    questions. `granted` is every badge the rules say is currently earned --
    the same list every run, once things settle. `new` is what this run
    actually created, which is the only part worth printing: a pass that
    reports fourteen badges every night trains whoever reads it to stop.

    Newness is decided by collecting the existing primary keys first rather
    than by comparing timestamps. A clock comparison would also catch a badge
    granted by a publish in another process while this was running, and an
    operator chasing an unexpected line in the output should not be sent after
    something that was correct. The set costs one column of one small table,
    and `Award` is a table that stays small by design -- §H.8 refuses every
    mechanism that would make it otherwise.
    """
    as_of = as_of or timezone.now()
    before = set(Award.objects.values_list('pk', flat=True))

    granted = []
    for listing in Listing.objects.visible().select_related(
        'owner_account', 'owner_organisation', 'contributed_by',
    ):
        granted.extend(award_published(listing))
        earned = award_sustained(listing, as_of=as_of)
        if earned is not None:
            granted.append(earned)

    return {
        'granted': granted,
        'new': [award for award in granted if award.pk not in before],
    }
