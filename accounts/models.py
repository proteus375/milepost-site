"""Marketplace identity: who this person is, and what other people see.

THIS APP IS WHY THE PROJECT NOW HAS A DATABASE. The settings file predicted
it: auth, sessions, messages and contenttypes arrive with `accounts`, "the app
that first needs a user", and until now the site had no models and needed no
database at all.

TWO IDENTITIES, AND KEEPING THEM APART IS THE WHOLE MODEL
---------------------------------------------------------
`email` is a credential. `handle` and `display_name` are a public identity.
They are separate fields because they are separate things, and a community
site that lets one stand in for the other has published somebody's email
address by way of a convenience.

Django's own `AbstractUser` invites exactly that mistake by shipping a
`username` that is both the login and the visible name. So this does not
extend it.

EMAIL IS UNIQUE HERE, DELIBERATELY UNLIKE THE LMS
--------------------------------------------------
`homeschool-lms` has a non-unique `User.email`, and the design document calls
that Defect 1 -- the flaw §C's OAuth bridge exists to route around, because
"the join key is an opaque subject id stored on the local user, never an email
address ... this is not a refinement, it is the thing that makes the bridge
sound at all".

This project is the identity provider in that bridge. Carrying the same defect
into the thing that is supposed to be authoritative about who somebody is
would be inheriting a bug on purpose. So: unique, case-insensitively, and the
normalisation happens on save rather than in a form, because a second way to
create an account must not be a second chance to get it wrong.

WHO MAY HAVE ONE OF THESE: ADULTS
----------------------------------
§5 of the design document is unambiguous -- "child logins are not a deferred
feature; they are a different product" -- and §4.4.7 argues that a guardian
entering everything is what most likely keeps Milepost clear of COPPA's
heaviest obligations. A public profile page carrying a child's name would
undo that in one release.

So an account is an adult's, and `terms_accepted_at` records that they said
so. NOT an age, and not a date of birth: those are facts about a person that
this product has no use for and should not hold. A timestamp records a thing
somebody DID, which is what is actually needed if the question is ever asked.

WHAT IS NOT HERE YET, AND WHY THAT IS NOT AN OVERSIGHT
-------------------------------------------------------
No email verification. It is the obvious anti-abuse primitive and §5 names
sockpuppet resistance as the hard problem -- but nothing on this site can yet
be farmed, published, reviewed or voted on, so a verification flow today would
guard nothing. It arrives with the first action that can be abused, which the
README's own rule would call the honest time for it.

No organisations. §C.4 designs them and says listings need an owner that
outlives a person; that is a `catalog` concern and arrives with listings.

No reputation. Points and badges attach here eventually -- §5 is explicit that
they attach to the person, never to the installation, or a family farms them
by standing up a second instance -- and there is nothing to attach to them
until people can publish and review. The profile page is the surface they will
hang from, which is most of why it exists this early.

When they arrive they should be recorded as awards with a reason and a date,
never as a running total on this model. A number nobody can explain is a
number nobody trusts, and this is the same argument the LMS just spent a
change on: a mark is a record of what happened, not a figure recomputed from
whatever the rules say today.
"""

import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

#: Lowercase letters, digits and single hyphens, 3-30 characters, not starting
#: or ending with a hyphen. Narrow on purpose: a handle appears in a URL and
#: beside somebody's words, so it has to be unmistakable when read aloud and
#: impossible to confuse with somebody else's at a glance.
HANDLE_PATTERN = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
HANDLE_MIN = 3
HANDLE_MAX = 30

#: Handles that must not be claimed by a person, because a URL or an email
#: that uses one would read as coming from Milepost itself. Not a moderation
#: list -- impersonation of the site is a different problem from an offensive
#: name, and this only solves the first one.
RESERVED_HANDLES = frozenset({
    'about', 'account', 'accounts', 'admin', 'administrator', 'api', 'billing',
    'blog', 'catalog', 'contact', 'help', 'home', 'legal', 'login', 'logout',
    'me', 'milepost', 'moderator', 'new', 'news', 'people', 'pricing',
    'privacy', 'root', 'security', 'settings', 'signin', 'signup', 'staff',
    'static', 'support', 'system', 'terms', 'themes', 'user', 'users',
})


def validate_handle(value):
    """The rules for a public handle, in one place.

    A validator rather than a form clean, so that every route to creating an
    account meets the same rules -- the admin, a management command, a future
    OAuth-driven signup. A rule enforced only by the form somebody happened to
    use is a rule that holds until the second way in is written.
    """
    if len(value) < HANDLE_MIN or len(value) > HANDLE_MAX:
        raise ValidationError(
            f'A handle is between {HANDLE_MIN} and {HANDLE_MAX} characters.'
        )
    if not HANDLE_PATTERN.match(value):
        raise ValidationError(
            'A handle can use lowercase letters, numbers and hyphens, and '
            'cannot start or end with a hyphen.'
        )
    if value in RESERVED_HANDLES:
        raise ValidationError('That handle is reserved.')


class AccountManager(BaseUserManager):
    """Creating accounts, with the normalisation in the one place.

    `create_user` rather than `Account.objects.create`: the email has to be
    lowercased and the password hashed, and a manager is the only place every
    caller reliably passes through.
    """

    use_in_migrations = True

    def _create(self, email, handle, password, **extra):
        if not email:
            raise ValueError('An account needs an email address.')
        if not handle:
            raise ValueError('An account needs a handle.')

        account = self.model(
            email=self.normalize_email(email).lower(),
            handle=handle.lower(),
            **extra,
        )
        account.set_password(password)
        account.full_clean(exclude=['password'])
        account.save(using=self._db)
        return account

    def create_user(self, email, handle, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._create(email, handle, password, **extra)

    def create_superuser(self, email, handle, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        if not extra['is_staff'] or not extra['is_superuser']:
            raise ValueError('A superuser is staff and superuser.')
        # An operator making the first account has accepted nothing; recording
        # `now` would be a claim nobody made. See `terms_accepted_at`.
        return self._create(email, handle, password, **extra)


class Account(AbstractBaseUser, PermissionsMixin):
    """One person on the marketplace.

    Named `Account` rather than `User` because this project has two kinds of
    person in its future -- somebody with a marketplace login, and somebody
    with a login on their family's own installation -- and calling both "user"
    is how §C's two-layer identity model gets collapsed by accident in
    conversation before it gets collapsed in code.
    """

    email = models.EmailField(
        unique=True,
        help_text='Used to sign in. Never shown to anybody else.',
    )
    handle = models.SlugField(
        max_length=HANDLE_MAX,
        unique=True,
        validators=[validate_handle],
        help_text='Your public name in addresses: milepost.example/people/you.',
    )
    display_name = models.CharField(
        max_length=60,
        blank=True,
        help_text='What people see. Your handle is used if you leave this blank.',
    )

    # Recorded as an act, not as an attribute. See the module docstring: this
    # says "on this date, this person confirmed they are an adult and accepted
    # the terms", which is the only thing anybody ever needs to know. An age
    # or a date of birth would be a fact about them that this product has no
    # use for.
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = AccountManager()

    USERNAME_FIELD = 'email'
    # `handle` is required at creation but is not the login. Django wants both
    # named so `createsuperuser` prompts for it.
    REQUIRED_FIELDS = ['handle']

    class Meta:
        ordering = ['handle']

    def __str__(self):
        return self.handle

    def clean(self):
        super().clean()
        self.email = (self.email or '').strip().lower()
        self.handle = (self.handle or '').strip().lower()

    def save(self, *args, **kwargs):
        # Normalised here as well as in the manager, because `save()` is the
        # one door every write goes through and the manager is not.
        self.email = (self.email or '').strip().lower()
        self.handle = (self.handle or '').strip().lower()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('profile', args=[self.handle])

    @property
    def public_name(self):
        """What to call this person in front of other people.

        Falls back to the handle rather than to the email, which is the whole
        point of having two fields. A bug here is a disclosure, not a display
        glitch, so it is a property with a name rather than a template
        expression repeated on every page that shows somebody.
        """
        return self.display_name.strip() or self.handle

    @property
    def has_accepted_terms(self):
        return self.terms_accepted_at is not None
