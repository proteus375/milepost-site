"""Who is paid up, and what that entitles them to.

WHAT THIS APP OWES THE REST OF THE SYSTEM IS ONE ANSWER
--------------------------------------------------------
*Is this subject entitled right now?* Everything else here exists to make that
answer true.

§B.3 of the design document describes a signed, expiring token carrying a set
of per-household entitlements, Ed25519, a daily refresh and two different
staleness rules. None of that is in this module, and its absence is a decision
rather than a first cut. **That token exists so an installation in the field
can verify entitlement offline** -- it is the transport, not the answer. There
is no `instances` app, so nothing consumes it, and building a signing key, a
key-distribution story and a grace-window rule for a message with no reader is
the kind of work that looks like progress. The token arrives with the thing
that needs it, and it will read exactly the state this module holds.

Marketplace-side, entitlement is checked in process, against a row.

THE UNIT IS THE HOUSEHOLD, AND §B.3 SETTLED WHY IT CANNOT BE ANYTHING ELSE
---------------------------------------------------------------------------
Not the guardian: two parents share one subscription, and billing each of them
would either double-charge a household or gate one parent out of their own
children's records. Not a family computed by the LMS: §3's Defect 2 is that it
cannot compute one -- there is no household model and no adult-to-adult link,
and inferring one from shared children breaks on separated parents and an
involved grandparent, which that model's own docstring calls ordinary.

So the humans decide who is on it, which §B.3 argues is the only correct way
to decide it. A separated couple maintains two households; a grandparent joins
one or holds their own.

ONE ACCOUNT, ONE HOUSEHOLD -- THE CONSTRAINT THAT BOUNDS THE ABUSE
-------------------------------------------------------------------
`one_household_per_account` is unique on `account` alone, not on the pair, and
it is the load-bearing anti-abuse rule in this file. Without it a single
subscription could be joined by unlimited identities and "one household, one
identity" -- a claim §5 says the platform actively depends on -- would be
unenforceable rather than merely unenforced.

WHAT A MEMBER CAP DOES, AND WHAT IT DOES NOT
----------------------------------------------
`MAX_HOUSEHOLD_MEMBERS` bounds how many marketplace identities one
subscription carries. It is worth stating plainly what problem that solves,
because the obvious answer is wrong.

It is **not** what stops sockpuppets. §H.6 settles that an acquisition, a
review and a threshold badge count once per household, so a household of
twenty earns exactly what a household of two earns. Extra members buy no
reputation at all, which is the entire point of counting per household -- the
cap could be lifted tomorrow and nothing in §H would move.

What it bounds is revenue leakage: ten unrelated families sharing one
per-family plan. That is a subscription-terms problem wearing a schema's
clothing, and six is chosen to be comfortably above a real household --
two guardians, a grandparent, room to spare -- and well below a co-op. A co-op
is an `Organisation` (§C.4), which is a different thing entirely and has no
subscription of its own; §C.4.6 leaves that question open and this module does
not answer it.

DEACTIVATED, NEVER DELETED
----------------------------
The fifth model in these two repositories to take this shape, after
`IntegrationToken`, `Material`, `Organisation` and `Listing`. Here the reason
is `Acquisition`: a household that lapses or winds up still acquired things,
and §4.4.3 makes that licence perpetual. A deleted household would take the
rows recording what it was entitled to with it, which is why every reference
to one is `PROTECT`.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

#: How many marketplace identities one subscription may carry. See the module
#: docstring: this bounds revenue leakage, not sockpuppets -- §H.6's
#: per-household counting is what bounds those, and it does so completely.
MAX_HOUSEHOLD_MEMBERS = 6

#: What an entitled household may do, from §B.3's token payload. A single
#: tuple rather than a per-plan set, because there is one plan (§B.2:
#: per-family, flat) and a features table with one row in it is a menu
#: pretending to be a mechanism -- the same argument §4.4.1 made about
#: licences. Per-feature variation arrives with a second plan, if one ever
#: does.
FEATURES = ('marketplace.download', 'marketplace.publish', 'content.shared')


class Household(models.Model):
    """One subscription, and the marketplace identities it covers."""

    #: What the members call it. Never shown to anybody outside it -- a
    #: household is a billing arrangement, not a public identity, and it has
    #: no slug for the same reason it has no profile page. `Account.handle`
    #: and `Organisation.slug` are the public names; adding a third would
    #: mean a third thing `refuse_a_taken_public_name` has to know about.
    name = models.CharField(
        max_length=120,
        help_text='What the people on it call it. Only they ever see it.',
    )

    # NOT A BOOLEAN, AND NOT A STATUS WORD. A date answers "entitled?" and
    # "until when?" with one field and no second source of truth, and it is
    # what §B.3's token carries per subject (`"through": "<date>"`) -- so the
    # machine transport, when it arrives, copies this rather than deriving it.
    #
    # Null means never entitled, which is what a household starts as. Set by
    # hand in the admin until Stripe writes it; that is the whole of the seam
    # between this half of `billing` and the other.
    entitled_through = models.DateField(
        null=True, blank=True,
        help_text=(
            'Paid up to and including this date. Blank means never entitled. '
            'Set by hand until Stripe sets it.'
        ),
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # `through_fields` is required for the same reason `Organisation.members`
    # needs it, and the reason is worth repeating rather than cross-
    # referencing: HouseholdMembership has TWO foreign keys to Account --
    # `account`, who the membership is for, and `added_by`, who granted it --
    # so "the members of this household" is ambiguous until it is said which
    # one it means. Django refuses to guess (fields.E335), and guessing wrong
    # would list the people who granted memberships as the people who hold
    # them.
    members = models.ManyToManyField(
        'accounts.Account',
        through='HouseholdMembership',
        through_fields=('household', 'account'),
        related_name='households',
    )

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name or f'household {self.pk}'

    @property
    def is_entitled(self):
        """Whether this household may reach other people's content today.

        Deliberately not "has a subscription". §B.4 draws the line at other
        people's content, and on the marketplace that is the only kind there
        is -- a family's own records live in their installation, which this
        service never gates. So one property answers the whole question here.
        """
        if not self.is_active or self.entitled_through is None:
            return False
        return self.entitled_through >= timezone.localdate()

    def owners(self):
        return self.memberships.filter(role=HouseholdMembership.Role.OWNER)

    def add_member(self, account, role=None, added_by=None):
        """Refuses a seventh member, and refuses somebody else's.

        Both checks are here rather than in a form, on the rule
        `validate_handle` already set in `accounts`: a rule enforced only by
        the form somebody happened to use is a rule that holds until the
        second way in is written. The unique constraint catches the second
        case at the database too; this exists so the failure is a sentence
        instead of an IntegrityError.
        """
        if self.memberships.count() >= MAX_HOUSEHOLD_MEMBERS:
            raise ValidationError(
                f'A household covers up to {MAX_HOUSEHOLD_MEMBERS} people. '
                'A larger group is a co-op, which is an organisation rather '
                'than a household.'
            )
        existing = HouseholdMembership.objects.filter(account=account).first()
        if existing is not None:
            if existing.household_id == self.pk:
                return existing
            raise ValidationError(
                'That person is already on another household. A marketplace '
                'account belongs to one household at a time.'
            )
        return HouseholdMembership.objects.create(
            household=self,
            account=account,
            role=role or HouseholdMembership.Role.MEMBER,
            added_by=added_by,
        )

    def remove_member(self, account):
        """Refuses to remove the last owner.

        The third time this codebase has written this refusal --
        `students.remove_guardian` in the LMS, `Organisation.remove_member`
        here -- and the failure is the same shape each time: a record nobody
        can manage. A household with no owner is a subscription nobody can
        cancel, change the card on, or take somebody off.
        """
        membership = self.memberships.filter(account=account).first()
        if membership is None:
            return
        if (
            membership.role == HouseholdMembership.Role.OWNER
            and self.owners().count() == 1
        ):
            raise ValidationError(
                'A household must keep at least one owner. Add another '
                'before removing this one.'
            )
        membership.delete()


class HouseholdMembership(models.Model):
    """Who a subscription covers, who put them on it, and when.

    A through model rather than a plain many-to-many, by the rule this
    codebase applies wherever it picks between the two: a plain M2M is right
    when there is nothing to record about the relationship beyond its
    existence, and the moment there is -- who granted it, when, with what
    remit -- it should be a through model. All three exist here.
    """

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        MEMBER = 'MEMBER', 'Member'

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name='memberships',
    )
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE,
        related_name='household_memberships',
    )
    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.MEMBER,
    )
    added_at = models.DateTimeField(default=timezone.now)
    # SET_NULL, on the precedent `OrganisationMembership.added_by` set: the
    # fact that somebody was put on a household is not undone by the person
    # who did it closing their account.
    added_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='household_memberships_granted',
    )

    class Meta:
        ordering = ['household', 'account']
        constraints = [
            # UNIQUE ON `account` ALONE, WHICH IS THE WHOLE POINT. A pair
            # constraint would say "not on this household twice" and permit
            # one person on six households -- six subscriptions' worth of
            # entitlement for one, and the door §5 calls sockpuppet
            # resistance. See the module docstring.
            models.UniqueConstraint(
                fields=['account'],
                name='one_household_per_account',
            ),
        ]

    def __str__(self):
        return f'{self.account.handle} on {self.household}'


def household_of(account):
    """The household this account is on, or None.

    None is an ordinary answer, not an error: signing up costs nothing and
    creates no household, and somebody browsing the catalogue has every right
    to be here without one. §C.6 is the rule this implements -- browse
    freely, link to acquire.
    """
    if not getattr(account, 'is_authenticated', False):
        return None
    membership = HouseholdMembership.objects.filter(
        account=account,
    ).select_related('household').first()
    return membership.household if membership else None


def is_entitled(account):
    """Whether this account may reach content it did not author."""
    household = household_of(account)
    return household is not None and household.is_entitled


def entitlement_refusal(account):
    """None when they may, or a sentence saying why not.

    A sentence rather than False, on the pattern `may_review` already set in
    `catalog`: every one of these refusals is something the person should be
    told, and a bare boolean at the call site becomes a generic message that
    explains nothing. The three cases really are different -- not signed in,
    signed in with no subscription, and a subscription that has lapsed -- and
    the third one especially should not read like the second.
    """
    if not getattr(account, 'is_authenticated', False):
        return 'Only people with a Milepost account can download a plan.'

    household = household_of(account)
    if household is None:
        return (
            'Downloading shared plans needs a subscription. Your account is '
            'not on a household yet.'
        )
    if not household.is_active:
        return 'That household is closed.'
    if not household.is_entitled:
        return (
            'That subscription has lapsed. Your own records are unaffected; '
            'what needs a live subscription is other people’s plans.'
        )
    return None
