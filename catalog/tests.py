"""The owner shape, and the terms that make a publication answerable.

WHAT THESE TESTS ARE ACTUALLY FOR. Two of the rules here are enforced by
database constraints, which means the way to test them is to try to write a
row that breaks one and watch the database refuse. That is worth doing rather
than trusting the migration: a CheckConstraint that was written but never
exercised is a comment with a syntax error waiting in it, and the first thing
to find out is whether it reaches the database at all.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account, Organisation, OrganisationMembership
from catalog.models import (
    CONTENT_LICENCE, PUBLISHER_TERMS_VERSION, Listing, Subject,
    TermsAcceptance, accept_terms, has_accepted,
)


class CatalogFixture(TestCase):
    def person(self, handle='ada'):
        return Account.objects.create_user(
            email=f'{handle}@example.com',
            handle=handle,
            password='a-long-enough-passphrase',
        )

    def co_op(self, slug='oak-hill', owner=None):
        organisation = Organisation(slug=slug, name='Oak Hill Co-op')
        organisation.full_clean()
        organisation.save()
        if owner is not None:
            organisation.add_member(
                owner, role=OrganisationMembership.Role.OWNER,
            )
        return organisation

    def plan(self, slug='botany', **extra):
        fields = {
            'title': 'A Year of Botany',
            'slug': slug,
            'summary': 'Thirty-six weeks of plants, mostly outdoors.',
            'subject': Subject.SCIENCE,
            'grade_min': 3,
            'grade_max': 6,
        }
        fields.update(extra)
        return Listing.objects.create(**fields)


class ExactlyOneOwnerTests(CatalogFixture):
    """§C.4.2's constraint, checked against the database rather than the model.

    Ownership is what survives a person leaving; a listing with two owners or
    none is a listing whose attribution has no answer.
    """

    def test_a_person_can_own_one(self):
        listing = self.plan(owner_account=self.person())
        self.assertEqual(listing.owner, listing.owner_account)

    def test_so_can_an_organisation(self):
        organisation = self.co_op()
        listing = self.plan(owner_organisation=organisation)
        self.assertEqual(listing.owner, organisation)

    def test_but_not_both(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.plan(
                owner_account=self.person(),
                owner_organisation=self.co_op(),
            )

    def test_and_not_neither(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.plan()

    def test_the_owner_answers_to_one_name_whichever_kind_it_is(self):
        """Both kinds of owner have `public_name`, which is why attribution
        can render either without asking what it is holding."""
        person = self.person()
        person.display_name = 'Ada L.'
        person.save()

        self.assertEqual(self.plan('a', owner_account=person).owner_name, 'Ada L.')
        self.assertEqual(
            self.plan('b', owner_organisation=self.co_op()).owner_name,
            'Oak Hill Co-op',
        )


class WhatSurvivesSomebodyLeavingTests(CatalogFixture):
    def test_an_organisations_listing_outlives_its_contributor(self):
        """The whole argument for organisation ownership, in one test.

        Priya publishes for the co-op and then deletes her account. The
        listing is still the co-op's; only the credit degrades."""
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        accept_terms(priya, accepted_by=priya)
        accept_terms(organisation, accepted_by=priya)
        listing = self.plan(owner_organisation=organisation).publish(by=priya)

        priya.delete()

        listing.refresh_from_db()
        self.assertEqual(listing.owner, organisation)
        self.assertIsNone(listing.contributed_by)
        self.assertTrue(listing.is_published)

    def test_a_personal_listing_goes_with_its_owner(self):
        """CASCADE, deliberately. §C.4 lists "the listings have no owner" as
        the decisive problem organisations exist to solve, so the honest
        behaviour for a listing with no organisation behind it is that it
        leaves with the person."""
        ada = self.person()
        self.plan(owner_account=ada)
        ada.delete()
        self.assertEqual(Listing.objects.count(), 0)

    def test_an_organisation_holding_listings_cannot_be_deleted(self):
        """PROTECT. `is_active` exists so a co-op is wound down rather than
        removed, and this makes that a rule rather than a convention."""
        organisation = self.co_op()
        self.plan(owner_organisation=organisation)
        with self.assertRaises(ProtectedError), transaction.atomic():
            organisation.delete()


class GradeRangeTests(CatalogFixture):
    def test_a_range_runs_forwards(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.plan(owner_account=self.person(), grade_min=6, grade_max=3)

    def test_one_grade_is_a_range_of_one(self):
        listing = self.plan(
            owner_account=self.person(), grade_min=4, grade_max=4,
        )
        self.assertEqual(listing.grade_range, 'Grade 4')

    def test_kindergarten_is_not_shown_as_a_zero(self):
        listing = self.plan(
            owner_account=self.person(), grade_min=0, grade_max=2,
        )
        self.assertEqual(listing.grade_range, 'Grades K–2')


class AcceptingTheTermsTests(CatalogFixture):
    def test_nobody_accepts_for_somebody_else(self):
        ada, priya = self.person('ada'), self.person('priya')
        with self.assertRaises(ValidationError):
            accept_terms(ada, accepted_by=priya)

    def test_an_owner_accepts_for_the_organisation(self):
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        acceptance = accept_terms(organisation, accepted_by=priya)

        self.assertEqual(acceptance.subject, organisation)
        self.assertEqual(acceptance.accepted_by, priya)
        self.assertTrue(has_accepted(organisation))

    def test_but_a_publisher_cannot(self):
        """Not a convenience check. `legal/publisher-terms.md` says it in the
        document people are agreeing to: an organisation accepts through one
        of its owners, because accepting is an ownership act."""
        organisation = self.co_op()
        ada = self.person()
        organisation.add_member(ada)
        with self.assertRaises(ValidationError):
            accept_terms(organisation, accepted_by=ada)

    def test_accepting_twice_records_once(self):
        ada = self.person()
        accept_terms(ada, accepted_by=ada)
        accept_terms(ada, accepted_by=ada)
        self.assertEqual(TermsAcceptance.objects.filter(account=ada).count(), 1)

    def test_a_new_version_is_a_new_row_not_an_edit(self):
        """Append-only. The history of who agreed to what, when, is the whole
        point, and an UPDATE would destroy the fact the model holds."""
        ada = self.person()
        accept_terms(ada, accepted_by=ada, version='1.0')
        accept_terms(ada, accepted_by=ada, version='2.0')

        self.assertEqual(
            sorted(TermsAcceptance.objects.values_list('terms_version', flat=True)),
            ['1.0', '2.0'],
        )

    def test_a_row_names_exactly_one_subject(self):
        ada = self.person()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TermsAcceptance.objects.create(
                account=ada, organisation=self.co_op(),
                accepted_by=ada, terms_version='1.0',
            )

    def test_the_record_survives_the_person_who_clicked(self):
        """SET_NULL. That the organisation accepted is not undone by the
        owner who clicked closing their account -- the organisation accepted,
        and it still exists."""
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        accept_terms(organisation, accepted_by=priya)
        priya.delete()

        acceptance = TermsAcceptance.objects.get(organisation=organisation)
        self.assertIsNone(acceptance.accepted_by)
        self.assertTrue(has_accepted(organisation))


class PublishingTests(CatalogFixture):
    def test_a_plan_starts_as_a_draft(self):
        self.assertEqual(
            self.plan(owner_account=self.person()).status, Listing.Status.DRAFT,
        )

    def test_and_is_not_visible_until_it_is_published(self):
        self.plan(owner_account=self.person())
        self.assertEqual(Listing.objects.visible().count(), 0)

    def test_publishing_needs_the_terms_accepted(self):
        ada = self.person()
        with self.assertRaises(ValidationError):
            self.plan(owner_account=ada).publish(by=ada)

    def test_and_records_which_version(self):
        ada = self.person()
        accept_terms(ada, accepted_by=ada)
        listing = self.plan(owner_account=ada).publish(by=ada)

        self.assertEqual(listing.terms_version, PUBLISHER_TERMS_VERSION)
        self.assertEqual(listing.licence, CONTENT_LICENCE)
        self.assertIsNotNone(listing.published_at)
        self.assertEqual(Listing.objects.visible().count(), 1)

    def test_and_who_contributed_it(self):
        ada = self.person()
        accept_terms(ada, accepted_by=ada)
        listing = self.plan(owner_account=ada).publish(by=ada)
        self.assertEqual(listing.contributed_by, ada)

    def test_somebody_elses_plan_is_not_yours_to_publish(self):
        ada, priya = self.person('ada'), self.person('priya')
        accept_terms(priya, accepted_by=priya)
        with self.assertRaises(ValidationError):
            self.plan(owner_account=ada).publish(by=priya)

    def test_publishing_for_an_organisation_needs_membership(self):
        priya, ada = self.person('priya'), self.person('ada')
        organisation = self.co_op(owner=priya)
        accept_terms(ada, accepted_by=ada)
        accept_terms(organisation, accepted_by=priya)

        with self.assertRaises(ValidationError):
            self.plan(owner_organisation=organisation).publish(by=ada)

    def test_and_the_organisations_own_acceptance(self):
        """Both warrant, §4.4.4. The contributor accepting is not the
        organisation accepting, and either alone leaves half the warranty
        unsigned."""
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        accept_terms(priya, accepted_by=priya)

        with self.assertRaises(ValidationError):
            self.plan(owner_organisation=organisation).publish(by=priya)

    def test_a_publisher_can_publish_even_though_they_cannot_accept(self):
        """The two rights are different, and this is the pair that shows it:
        Ada may publish for the co-op, and may not agree to anything on its
        behalf. Priya's acceptance is what makes Ada's publish possible."""
        priya, ada = self.person('priya'), self.person('ada')
        organisation = self.co_op(owner=priya)
        organisation.add_member(ada)
        accept_terms(ada, accepted_by=ada)
        accept_terms(organisation, accepted_by=priya)

        listing = self.plan(owner_organisation=organisation).publish(by=ada)
        self.assertTrue(listing.is_published)
        self.assertEqual(listing.contributed_by, ada)
        self.assertEqual(listing.owner, organisation)

    def test_a_closed_organisation_publishes_nothing(self):
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        accept_terms(priya, accepted_by=priya)
        accept_terms(organisation, accepted_by=priya)
        organisation.is_active = False
        organisation.save()

        with self.assertRaises(ValidationError):
            self.plan(owner_organisation=organisation).publish(by=priya)


class WhoMayReadOneTests(CatalogFixture):
    def test_a_published_plan_is_public(self):
        ada = self.person()
        accept_terms(ada, accepted_by=ada)
        listing = self.plan(owner_account=ada).publish(by=ada)
        self.assertTrue(listing.may_be_read_by(None))

    def test_a_draft_is_not(self):
        self.assertFalse(self.plan(owner_account=self.person()).may_be_read_by(None))

    def test_but_its_owner_can_see_it(self):
        ada = self.person()
        self.assertTrue(self.plan(owner_account=ada).may_be_read_by(ada))

    def test_and_a_stranger_cannot(self):
        ada, priya = self.person('ada'), self.person('priya')
        self.assertFalse(self.plan(owner_account=ada).may_be_read_by(priya))

    def test_a_co_ops_draft_is_visible_to_its_members(self):
        priya, ada = self.person('priya'), self.person('ada')
        organisation = self.co_op(owner=priya)
        organisation.add_member(ada)
        listing = self.plan(owner_organisation=organisation)

        self.assertTrue(listing.may_be_read_by(ada))
        self.assertFalse(listing.may_be_read_by(self.person('stranger')))


class BrowsingTests(CatalogFixture):
    def published(self, slug='botany', owner=None, **extra):
        owner = owner or self.person()
        accept_terms(owner, accepted_by=owner)
        return self.plan(slug, owner_account=owner, **extra).publish(by=owner)

    def test_the_catalogue_lists_published_plans(self):
        self.published()
        response = self.client.get(reverse('plans'))
        self.assertContains(response, 'A Year of Botany')

    def test_and_not_drafts(self):
        self.plan(owner_account=self.person())
        response = self.client.get(reverse('plans'))
        self.assertNotContains(response, 'A Year of Botany')

    def test_it_says_so_when_there_is_nothing(self):
        """The state this page ships in, so it is a written sentence rather
        than an empty list."""
        self.assertContains(
            self.client.get(reverse('plans')), 'No plans have been published',
        )

    def test_it_filters_by_subject(self):
        self.published('botany', subject=Subject.SCIENCE)
        response = self.client.get(reverse('plans'), {'subject': Subject.MATHEMATICS})
        self.assertNotContains(response, 'A Year of Botany')

    def test_an_unknown_subject_is_ignored_rather_than_an_error(self):
        self.published()
        response = self.client.get(reverse('plans'), {'subject': 'BOTANY'})
        self.assertContains(response, 'A Year of Botany')

    def test_a_published_plan_has_a_page(self):
        listing = self.published()
        response = self.client.get(listing.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thirty-six weeks')

    def test_a_draft_is_a_404_to_a_stranger(self):
        """Not a 403. Whether an address belongs to anything is not something
        a stranger is owed -- the same rule the profile page follows."""
        listing = self.plan(owner_account=self.person())
        self.assertEqual(self.client.get(listing.get_absolute_url()).status_code, 404)

    def test_but_its_owner_can_open_it(self):
        ada = self.person()
        listing = self.plan(owner_account=ada)
        self.client.force_login(ada)
        response = self.client.get(listing.get_absolute_url())
        self.assertContains(response, 'Draft')

    def test_a_personal_listing_does_not_credit_the_owner_twice(self):
        """"Published by Ada, contributed by Ada" reads like a bug, because
        on a personal listing the two fields are the same person."""
        listing = self.published()
        response = self.client.get(listing.get_absolute_url())
        self.assertNotContains(response, 'contributed by')

    def test_an_organisations_listing_credits_both(self):
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        accept_terms(priya, accepted_by=priya)
        accept_terms(organisation, accepted_by=priya)
        listing = self.plan(owner_organisation=organisation).publish(by=priya)

        response = self.client.get(listing.get_absolute_url())
        self.assertContains(response, 'Oak Hill Co-op')
        self.assertContains(response, 'contributed by')

    def test_a_profile_shows_that_persons_published_plans(self):
        ada = self.person()
        self.published(owner=ada)
        response = self.client.get(reverse('profile', args=['ada']))
        self.assertContains(response, 'A Year of Botany')

    def test_and_not_their_drafts(self):
        ada = self.person()
        self.plan(owner_account=ada)
        response = self.client.get(reverse('profile', args=['ada']))
        self.assertNotContains(response, 'A Year of Botany')


class WritingAPlanTests(CatalogFixture):
    def payload(self, **extra):
        fields = {
            'title': 'A Year of Botany',
            'summary': 'Thirty-six weeks of plants, mostly outdoors.',
            'description': '',
            'subject': Subject.SCIENCE,
            'grade_min': '3',
            'grade_max': '6',
            'owner': 'me',
        }
        fields.update(extra)
        return fields

    def test_a_stranger_is_sent_to_sign_in(self):
        response = self.client.get(reverse('new_plan'))
        self.assertIn(reverse('login'), response.url)

    def test_it_starts_as_a_draft_owned_by_you(self):
        ada = self.person()
        self.client.force_login(ada)
        self.client.post(reverse('new_plan'), self.payload())

        listing = Listing.objects.get()
        self.assertEqual(listing.owner, ada)
        self.assertEqual(listing.status, Listing.Status.DRAFT)
        self.assertEqual(listing.slug, 'a-year-of-botany')

    def test_a_second_plan_of_the_same_name_gets_its_own_address(self):
        """Suffixed rather than refused, as `portability.unique_code` does
        for course codes: two people may reasonably write "A Year of
        Botany", and telling the second their title is taken is a worse
        answer."""
        ada = self.person()
        self.client.force_login(ada)
        self.client.post(reverse('new_plan'), self.payload())
        self.client.post(reverse('new_plan'), self.payload())

        self.assertEqual(
            sorted(Listing.objects.values_list('slug', flat=True)),
            ['a-year-of-botany', 'a-year-of-botany-2'],
        )

    def test_a_title_that_would_shadow_a_page_is_refused(self):
        self.client.force_login(self.person())
        self.client.post(reverse('new_plan'), self.payload(title='New'))
        self.assertEqual(Listing.objects.count(), 0)

    def test_you_can_publish_for_a_co_op_you_belong_to(self):
        ada = self.person()
        organisation = self.co_op()
        organisation.add_member(ada)
        self.client.force_login(ada)
        self.client.post(reverse('new_plan'), self.payload(owner='oak-hill'))

        self.assertEqual(Listing.objects.get().owner, organisation)

    def test_but_not_for_one_you_do_not(self):
        self.co_op()
        self.client.force_login(self.person())
        self.client.post(reverse('new_plan'), self.payload(owner='oak-hill'))
        self.assertEqual(Listing.objects.count(), 0)

    def test_the_grade_range_has_to_run_forwards(self):
        self.client.force_login(self.person())
        response = self.client.post(
            reverse('new_plan'), self.payload(grade_min='6', grade_max='3'),
        )
        self.assertEqual(Listing.objects.count(), 0)
        self.assertContains(response, 'comes after')

    def test_the_owner_cannot_be_changed_by_editing(self):
        """Moving a listing between a person and a co-op is a transfer of
        ownership -- the thing §C.4 is about -- not an edit to a field."""
        ada = self.person()
        listing = self.plan(owner_account=ada)
        self.client.force_login(ada)
        self.client.post(
            reverse('edit_plan', args=[listing.slug]),
            self.payload(owner='oak-hill'),
        )

        listing.refresh_from_db()
        self.assertEqual(listing.owner, ada)

    def test_the_address_does_not_move_when_the_title_does(self):
        ada = self.person()
        listing = self.plan(owner_account=ada)
        self.client.force_login(ada)
        self.client.post(
            reverse('edit_plan', args=[listing.slug]),
            self.payload(title='A Year of Beetles'),
        )

        listing.refresh_from_db()
        self.assertEqual(listing.title, 'A Year of Beetles')
        self.assertEqual(listing.slug, 'botany')

    def test_somebody_elses_draft_cannot_be_edited(self):
        listing = self.plan(owner_account=self.person('ada'))
        self.client.force_login(self.person('priya'))
        self.assertEqual(
            self.client.get(reverse('edit_plan', args=[listing.slug])).status_code,
            404,
        )

    def test_a_published_plan_is_not_edited_in_place(self):
        """What people downloaded is what the manifest said it was. Changing
        the thing behind a version somebody already holds is the failure
        `version` exists to prevent."""
        ada = self.person()
        accept_terms(ada, accepted_by=ada)
        listing = self.plan(owner_account=ada).publish(by=ada)
        self.client.force_login(ada)

        self.assertEqual(
            self.client.get(reverse('edit_plan', args=[listing.slug])).status_code,
            404,
        )


class FindingYourOwnPlansAgainTests(CatalogFixture):
    """A draft with no address anybody can find is a draft that is lost.

    This page exists because verifying the previous commit meant reading the
    database to answer "where did that plan go" -- the catalogue lists
    published plans, a profile lists published plans, and nothing led back to
    a draft. Somebody who starts a plan and closes the tab had written
    something the site would never offer them again.
    """

    def test_a_stranger_is_sent_to_sign_in(self):
        response = self.client.get(reverse('your_plans'))
        self.assertIn(reverse('login'), response.url)

    def test_your_draft_is_here(self):
        ada = self.person()
        self.plan(owner_account=ada)
        self.client.force_login(ada)
        self.assertContains(self.client.get(reverse('your_plans')), 'A Year of Botany')

    def test_and_somebody_elses_is_not(self):
        self.plan(owner_account=self.person('ada'))
        self.client.force_login(self.person('priya'))
        self.assertNotContains(
            self.client.get(reverse('your_plans')), 'A Year of Botany',
        )

    def test_a_co_ops_draft_is_here_for_everybody_who_may_publish_it(self):
        """The point of an organisation owning a listing: a co-op's draft is
        not the private property of whoever opened the form."""
        priya, ada = self.person('priya'), self.person('ada')
        organisation = self.co_op(owner=priya)
        organisation.add_member(ada)
        self.plan(owner_organisation=organisation)

        self.client.force_login(ada)
        self.assertContains(self.client.get(reverse('your_plans')), 'A Year of Botany')

    def test_it_appears_once_even_for_an_owner_who_is_also_a_member(self):
        """The join over memberships duplicates a row per membership without
        `distinct`, and one plan listed twice is a bug people report."""
        priya = self.person('priya')
        organisation = self.co_op(owner=priya)
        self.plan(owner_organisation=organisation)

        self.client.force_login(priya)
        response = self.client.get(reverse('your_plans'))
        self.assertEqual(response.content.count(b'A Year of Botany'), 1)

    def test_a_published_plan_of_yours_is_here_too(self):
        ada = self.person()
        accept_terms(ada, accepted_by=ada)
        self.plan(owner_account=ada).publish(by=ada)

        self.client.force_login(ada)
        self.assertContains(self.client.get(reverse('your_plans')), 'Published')

    def test_it_says_so_when_there_is_nothing(self):
        self.client.force_login(self.person())
        self.assertContains(
            self.client.get(reverse('your_plans')), 'not started a plan yet',
        )


class WhatADraftSaysAboutItselfTests(CatalogFixture):
    def test_a_draft_does_not_claim_to_be_published(self):
        ada = self.person()
        listing = self.plan(owner_account=ada)
        self.client.force_login(ada)

        response = self.client.get(listing.get_absolute_url())
        self.assertNotContains(response, 'Published by')
        self.assertContains(response, 'Will be published by')
