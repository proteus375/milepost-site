"""The first tests in this repository, on the first app with models.

WHAT IS WORTH PINNING HERE
--------------------------
Not "does a form save". The things that are expensive to get wrong, and that
this app exists to get right:

  * EMAIL IS UNIQUE, CASE-INSENSITIVELY. `homeschool-lms` has a non-unique
    `User.email` and the design document calls it Defect 1 -- the flaw §C's
    OAuth bridge exists to route around. This project is the identity provider
    in that bridge; carrying the same defect into the authoritative side would
    be inheriting a bug on purpose.

  * THE PUBLIC PAGE PUBLISHES NOTHING PRIVATE. The whole reason `handle` and
    `email` are separate fields is that one of them is a credential. A test
    that only checked the page renders would not notice the day somebody
    "helpfully" adds the email to it.

  * HANDLES ARE ADDRESSES. They are reserved against the site's own paths,
    they are validated on the model rather than in a form, and nobody can
    change theirs -- an address other people have linked to must not quietly
    move and free itself for somebody else to take.

  * ACCOUNTS ARE ADULTS', RECORDED AS AN ACT. §5 is unambiguous that a child
    account is a different product. What is stored is that somebody confirmed
    it, on a date -- not an age, and never a date of birth.

WHAT THE FIRST RUN OF THESE FOUND
---------------------------------
Not a bug in `accounts`. Eight of these died on "Missing staticfiles manifest
entry for css/site.css", because the project ships
`CompressedManifestStaticFilesStorage` and `collectstatic` has not run under
test -- so every template extending base.html raised. That configuration
predates this app by every commit in the repository; there was simply nothing
rendering a template in a test to trip over it. See the note on STORAGES in
settings.py.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .forms import ProfileForm, SignUpForm
from .models import Account, validate_handle


class AccountFixture(TestCase):
    def make(self, handle='ada', email=None, **extra):
        return Account.objects.create_user(
            email=email or f'{handle}@example.com',
            handle=handle,
            password='a-long-enough-passphrase',
            **extra,
        )


class TheEmailIsACredentialTests(AccountFixture):
    def test_two_accounts_cannot_share_an_email(self):
        self.make('ada', email='ada@example.com')
        with self.assertRaises(ValidationError):
            self.make('grace', email='ada@example.com')

    def test_nor_the_same_email_in_different_case(self):
        """Django checks `unique` against the value as typed, so without
        normalisation Ada@ and ada@ are two accounts and one mailbox --
        Defect 1 arriving by a different route."""
        self.make('ada', email='ada@example.com')
        with self.assertRaises(ValidationError):
            self.make('grace', email='Ada@Example.com')

    def test_it_is_stored_lowercased(self):
        account = self.make('ada', email='Ada@Example.COM')
        self.assertEqual(account.email, 'ada@example.com')

    def test_it_never_appears_on_the_public_page(self):
        """The reason `handle` exists as a separate field."""
        self.make('ada', email='ada@example.com')
        response = self.client.get(reverse('profile', args=['ada']))
        self.assertNotContains(response, 'ada@example.com')


class HandlesAreAddressesTests(AccountFixture):
    def test_a_reserved_handle_is_refused(self):
        """Otherwise /people/admin/ reads as coming from Milepost itself."""
        with self.assertRaises(ValidationError):
            validate_handle('admin')

    def test_the_shape_is_enforced(self):
        for bad in ('ab', 'Ada', 'has space', '-leading', 'trailing-', 'a--b'):
            with self.subTest(handle=bad):
                with self.assertRaises(ValidationError):
                    validate_handle(bad)

    def test_a_reasonable_one_is_allowed(self):
        for good in ('ada', 'ada-lovelace', 'family7', 'a-b-c'):
            with self.subTest(handle=good):
                validate_handle(good)

    def test_it_is_validated_on_the_model_not_just_the_form(self):
        """A rule enforced by whichever form somebody used is a rule that
        lasts until the second way in is written."""
        with self.assertRaises(ValidationError):
            self.make('admin')

    def test_it_is_stored_lowercased(self):
        self.assertEqual(self.make('Ada'.lower()).handle, 'ada')

    def test_nobody_can_change_their_own(self):
        """An address other people may have linked to must not move silently,
        and the old one must not become free for somebody else to take."""
        from .forms import ProfileForm

        self.assertNotIn('handle', ProfileForm().fields)


class WhatOtherPeopleSeeTests(AccountFixture):
    def test_the_display_name_is_used_when_there_is_one(self):
        account = self.make('ada', display_name='Ada L.')
        self.assertEqual(account.public_name, 'Ada L.')

    def test_and_the_handle_when_there_is_not(self):
        """Falls back to the handle, never to the email. A bug here is a
        disclosure rather than a display glitch."""
        self.assertEqual(self.make('ada').public_name, 'ada')

    def test_a_profile_page_is_public(self):
        self.make('ada', display_name='Ada L.')
        response = self.client.get(reverse('profile', args=['ada']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ada L.')

    def test_a_handle_is_found_whatever_case_is_typed(self):
        self.make('ada')
        self.assertEqual(
            self.client.get(reverse('profile', args=['ADA'])).status_code, 200,
        )

    def test_a_deactivated_account_is_not_found(self):
        """404 rather than a page saying somebody was here. Whether a handle
        belongs to a deactivated account is not a stranger's business, and
        answering it makes this a way to enumerate who ever signed up."""
        self.make('ada', is_active=False)
        self.assertEqual(
            self.client.get(reverse('profile', args=['ada'])).status_code, 404,
        )


class SigningUpTests(TestCase):
    def payload(self, **extra):
        data = {
            'email': 'Ada@Example.com',
            'handle': 'ada',
            'display_name': 'Ada L.',
            'password1': 'a-long-enough-passphrase',
            'password2': 'a-long-enough-passphrase',
            'confirms_adult': 'on',
        }
        data.update(extra)
        return data

    def test_it_creates_an_account_and_signs_them_in(self):
        response = self.client.post(reverse('sign_up'), self.payload())
        self.assertRedirects(response, reverse('profile', args=['ada']))
        self.assertTrue(Account.objects.filter(handle='ada').exists())

    def test_the_email_is_normalised_before_the_uniqueness_check(self):
        Account.objects.create_user(
            email='ada@example.com', handle='other', password='pw-long-enough',
        )
        response = self.client.post(reverse('sign_up'), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Account.objects.filter(handle='ada').exists())

    def test_it_refuses_without_the_adult_confirmation(self):
        """§5: a child account is a different product, not a deferred one."""
        response = self.client.post(
            reverse('sign_up'), self.payload(confirms_adult=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Account.objects.exists())

    def test_the_confirmation_is_recorded_as_an_act_not_an_age(self):
        """A timestamp says somebody confirmed it on a date, which is all
        anybody needs. An age would be a fact about them this product has no
        use for and, for a minor, must not hold."""
        self.client.post(reverse('sign_up'), self.payload())
        account = Account.objects.get(handle='ada')
        self.assertIsNotNone(account.terms_accepted_at)

        field_names = {f.name for f in Account._meta.get_fields()}
        self.assertNotIn('date_of_birth', field_names)
        self.assertNotIn('age', field_names)

    def test_a_reserved_handle_is_refused_at_signup_too(self):
        response = self.client.post(
            reverse('sign_up'), self.payload(handle='admin'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Account.objects.exists())


class EditingYourProfileTests(AccountFixture):
    def test_a_stranger_is_sent_to_sign_in(self):
        response = self.client.get(reverse('edit_profile'))
        self.assertIn(reverse('login'), response.url)

    def test_the_owner_can_change_their_display_name(self):
        account = self.make('ada')
        self.client.force_login(account)
        self.client.post(reverse('edit_profile'), {'display_name': 'Ada L.'})

        account.refresh_from_db()
        self.assertEqual(account.display_name, 'Ada L.')

    def test_the_edit_link_is_only_on_your_own_page(self):
        """Asserted on the words, not on `/me/`.

        This used to check that the URL was absent, which stopped being a
        statement about this page the moment the masthead started linking
        every signed-in reader to their own profile. A test that fails
        because a header gained a link was testing the wrong thing; what is
        actually claimed here is that Grace is not invited to edit Ada.
        """
        self.make('ada')
        grace = self.make('grace')
        self.client.force_login(grace)

        response = self.client.get(reverse('profile', args=['ada']))
        self.assertNotContains(response, 'Edit your profile')

    def test_and_it_is_on_your_own_page(self):
        """The other half. Without this, deleting the link passes."""
        grace = self.make('grace')
        self.client.force_login(grace)

        response = self.client.get(reverse('profile', args=['grace']))
        self.assertContains(response, 'Edit your profile')


class TheMastheadTests(AccountFixture):
    """A feature nobody can reach is not shipped.

    Everything above tests the account pages by asking for their URLs
    directly, which is exactly how they were verified while being written,
    and exactly why the site could have gone out with no route to any of
    them from anywhere.
    """

    def test_a_stranger_is_offered_both_doors(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('login'))
        self.assertContains(response, reverse('sign_up'))

    def test_a_member_is_offered_their_own_name_instead(self):
        self.client.force_login(self.make('ada', display_name='Ada L.'))
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Ada L.')
        self.assertContains(response, reverse('logout'))
        self.assertNotContains(response, reverse('sign_up'))

    def test_the_masthead_never_shows_an_email(self):
        """`public_name` in the header, not `user`. Django's default
        `str(user)` is USERNAME_FIELD, which here is the email -- so
        `{{ user }}` would have published a credential on every page."""
        self.client.force_login(self.make('ada'))
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'ada@example.com')

    def test_signing_out_is_not_a_link(self):
        """A GET that ends a session can be fired by an <img> tag."""
        self.client.force_login(self.make('ada'))
        self.assertNotContains(
            self.client.get(reverse('home')),
            f'href="{reverse("logout")}"',
        )


class WhatTheBrowserFillsInTests(TestCase):
    """The display name is public, and a browser will guess at it.

    The first real signup produced a display name that was the local part of
    the signer-up's email address -- offered by a password manager, accepted
    by a blank text field, published on a public page. No code derived it and
    no test could have caught it, because the defect was in what the form
    failed to say about itself.
    """

    def test_the_email_claims_the_login_field(self):
        form = SignUpForm()
        self.assertIn('autocomplete="username"', str(form['email']))

    def test_the_display_name_says_what_it_is(self):
        form = SignUpForm()
        self.assertIn('autocomplete="nickname"', str(form['display_name']))

    def test_and_says_so_on_the_edit_form_too(self):
        self.assertIn('autocomplete="nickname"', str(ProfileForm()['display_name']))
