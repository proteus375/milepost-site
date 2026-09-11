"""What entitlement is, and the one constraint the rest of it rests on.

TWO OF THESE TESTS ARE ABOUT A DATABASE CONSTRAINT rather than about a method,
and `catalog.tests` already wrote down why that is worth doing: a
UniqueConstraint that was written but never exercised is a comment with a
syntax error waiting in it, and the first thing to find out is whether it
reaches the database at all. `one_household_per_account` is the rule that
stops one person collecting six subscriptions' worth of entitlement, so it is
tested by trying to break it and watching the database refuse -- not by
trusting `add_member`, which is the polite door and not the only one.

THE DATES ARE THE OTHER HALF. `entitled_through` is the seam between this half
of billing and the Stripe half that will eventually write it, which means
every boundary around "today" is a thing an operator will hit on a real
support call. Yesterday, today and tomorrow are each their own test.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account

from .models import (
    MAX_HOUSEHOLD_MEMBERS, Household, HouseholdMembership,
    entitlement_refusal, household_of, is_entitled,
)


class BillingFixture(TestCase):
    def person(self, handle='ada'):
        return Account.objects.create_user(
            email=f'{handle}@example.com',
            handle=handle,
            password='a-long-enough-passphrase',
        )

    def household(self, *accounts, through=None, name='The Lovelaces'):
        home = Household.objects.create(name=name, entitled_through=through)
        for position, account in enumerate(accounts):
            home.add_member(
                account,
                role=(
                    HouseholdMembership.Role.OWNER if position == 0
                    else HouseholdMembership.Role.MEMBER
                ),
            )
        return home

    def paid(self, *accounts, **extra):
        return self.household(
            *accounts, through=timezone.localdate() + timedelta(days=30),
            **extra,
        )


class OneHouseholdPerAccountTests(BillingFixture):
    """The load-bearing anti-abuse rule in this app.

    A pair constraint would read naturally and permit one person on six
    households -- six subscriptions' worth of entitlement for the price of
    one. §5 calls that door sockpuppet resistance; §B.3 is what opens it, by
    settling that a household carries one or more linked identities and
    letting the humans decide which.
    """

    def test_the_database_refuses_a_second_household(self):
        ada = self.person()
        self.paid(ada)
        other = Household.objects.create(name='Somebody else')

        with self.assertRaises(IntegrityError), transaction.atomic():
            HouseholdMembership.objects.create(household=other, account=ada)

    def test_and_add_member_refuses_it_with_a_sentence(self):
        """The constraint is the guarantee; this is so the failure is
        readable. An IntegrityError in front of an operator is a bug report."""
        ada = self.person()
        self.paid(ada)
        other = Household.objects.create(name='Somebody else')

        with self.assertRaises(ValidationError) as refused:
            other.add_member(ada)
        self.assertIn('already on another household', str(refused.exception))

    def test_adding_somebody_already_here_changes_nothing(self):
        """Idempotent rather than an error: the operator asked for a state
        that already holds, and refusing would make a retry into a failure."""
        ada = self.person()
        home = self.paid(ada)

        home.add_member(ada)
        self.assertEqual(home.memberships.count(), 1)

    def test_a_household_holds_more_than_one_person(self):
        """The case the whole model exists for -- two parents, one
        subscription. §B.3: billing each of them would double-charge a
        household or gate one parent out of their own children's records."""
        ada, priya = self.person('ada'), self.person('priya')
        home = self.paid(ada)
        home.add_member(priya)

        self.assertEqual(home.memberships.count(), 2)
        self.assertTrue(is_entitled(priya))


class HouseholdSizeTests(BillingFixture):
    """What the cap does, and what it does not.

    It is not what stops sockpuppets. §H.6 settles that an acquisition, a
    review and a threshold badge count once per household, so a household of
    twenty earns exactly what a household of two earns -- the cap could be
    lifted and nothing in §H would move. What it bounds is ten unrelated
    families sharing one per-family plan.
    """

    def test_a_household_fills_up(self):
        home = self.paid()
        for n in range(MAX_HOUSEHOLD_MEMBERS):
            home.add_member(self.person(f'person-{n}'))

        with self.assertRaises(ValidationError) as refused:
            home.add_member(self.person('one-too-many'))
        self.assertIn('co-op', str(refused.exception))

    def test_a_real_household_fits_comfortably(self):
        """Two guardians and a grandparent, which §B.3 calls the ordinary
        shape. If this ever fails the cap is wrong, not the family."""
        home = self.paid()
        for handle in ('mum', 'dad', 'grandma'):
            home.add_member(self.person(handle))
        self.assertEqual(home.memberships.count(), 3)


class IsEntitledTests(BillingFixture):
    def test_a_new_household_is_not_entitled(self):
        """Blank means never entitled, which is what signing up gets you.
        §C.6: browse freely, link to acquire."""
        self.assertFalse(self.household().is_entitled)

    def test_nor_is_one_whose_date_has_passed(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        self.assertFalse(self.household(through=yesterday).is_entitled)

    def test_the_last_day_still_counts(self):
        """Paid up to and including. An off-by-one here is a support call
        from somebody who paid for today."""
        self.assertTrue(
            self.household(through=timezone.localdate()).is_entitled,
        )

    def test_and_so_does_tomorrow(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertTrue(self.household(through=tomorrow).is_entitled)

    def test_a_closed_household_is_not_entitled_whatever_the_date(self):
        """Two fields, one answer. Reading entitlement off the date alone is
        the arithmetic a support call gets wrong, which is why the admin
        shows the property rather than only the column."""
        home = self.paid()
        home.is_active = False
        self.assertFalse(home.is_entitled)


class WhichHouseholdTests(BillingFixture):
    def test_somebody_signed_out_has_none(self):
        self.assertIsNone(household_of(None))

    def test_so_does_somebody_who_only_signed_up(self):
        """Not an error. Signing up costs nothing and creates no household,
        and browsing needs neither."""
        self.assertIsNone(household_of(self.person()))

    def test_a_member_has_theirs(self):
        ada = self.person()
        home = self.paid(ada)
        self.assertEqual(household_of(ada), home)


class RefusalsAreSentencesTests(BillingFixture):
    """Three different reasons, three different sentences.

    The pattern `may_review` set in `catalog`: a bare boolean at the call
    site turns into a generic message that explains nothing. The third case
    especially must not read like the second -- somebody whose subscription
    lapsed has not failed to subscribe, and telling them so is how a renewal
    turns into a support ticket.
    """

    def test_signed_out(self):
        self.assertIn('Milepost account', entitlement_refusal(None))

    def test_no_household(self):
        self.assertIn('not on a household', entitlement_refusal(self.person()))

    def test_lapsed_says_lapsed_and_reassures(self):
        """§B.4's principle, in the one sentence a person actually reads: a
        lapsed subscription must not lock a family out of their own data,
        and the refusal should say which kind of thing is gated."""
        ada = self.person()
        self.household(ada, through=timezone.localdate() - timedelta(days=1))

        refusal = entitlement_refusal(ada)
        self.assertIn('lapsed', refusal)
        self.assertIn('own records are unaffected', refusal)

    def test_a_closed_household_says_so(self):
        ada = self.person()
        home = self.paid(ada)
        home.is_active = False
        home.save(update_fields=['is_active'])

        self.assertIn('closed', entitlement_refusal(ada))

    def test_and_a_paid_up_member_is_refused_nothing(self):
        self.assertIsNone(entitlement_refusal(self.paid(self.person()).members.get()))


class LeavingAHouseholdTests(BillingFixture):
    """The third time this codebase has written the last-owner refusal --
    `students.remove_guardian` in the LMS, `Organisation.remove_member`
    here -- and the failure is the same shape each time: a record nobody can
    manage. A household with no owner is a subscription nobody can cancel.
    """

    def test_the_last_owner_stays(self):
        ada = self.person()
        home = self.paid(ada)

        with self.assertRaises(ValidationError) as refused:
            home.remove_member(ada)
        self.assertIn('at least one owner', str(refused.exception))

    def test_but_an_owner_can_go_once_there_is_another(self):
        ada, priya = self.person('ada'), self.person('priya')
        home = self.paid(ada)
        home.add_member(priya, role=HouseholdMembership.Role.OWNER)

        home.remove_member(ada)
        self.assertEqual(home.owners().count(), 1)

    def test_a_member_can_always_go(self):
        ada, priya = self.person('ada'), self.person('priya')
        home = self.paid(ada)
        home.add_member(priya)

        home.remove_member(priya)
        self.assertIsNone(household_of(priya))

    def test_and_can_then_join_another(self):
        """The separated-couple case §B.3 names. It has to work, or leaving a
        household is a one-way door into never subscribing again."""
        priya = self.person('priya')
        first = self.paid(self.person('ada'))
        first.add_member(priya)
        first.remove_member(priya)

        second = self.paid(self.person('sam'), name='The Sams')
        second.add_member(priya)
        self.assertEqual(household_of(priya), second)

    def test_removing_somebody_who_is_not_here_is_not_an_error(self):
        self.assertIsNone(self.paid(self.person('ada')).remove_member(
            self.person('stranger'),
        ))


class WhoGrantedItTests(BillingFixture):
    def test_the_grant_outlives_the_person_who_made_it(self):
        """SET_NULL, on the precedent `OrganisationMembership.added_by` set.
        Somebody being on a household is not undone by the person who put
        them there closing their account."""
        ada, priya = self.person('ada'), self.person('priya')
        home = self.paid(ada)
        home.add_member(priya, added_by=ada)

        ada.delete()
        membership = HouseholdMembership.objects.get(account=priya)
        self.assertIsNone(membership.added_by)
        self.assertEqual(membership.household, home)
