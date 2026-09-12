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

import base64
import hashlib
import re
import secrets
import uuid

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
        # An ordinary account is a member, so this door publishes. The signup
        # form does not come through here -- a ModelForm builds the instance
        # itself -- so it says the same thing in its own `save()`.
        extra.setdefault('is_public', True)
        return self._create(email, handle, password, **extra)

    def create_superuser(self, email, handle, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        if not extra['is_staff'] or not extra['is_superuser']:
            raise ValueError('A superuser is staff and superuser.')
        # NOT `setdefault`. An operator account is a login and nothing else,
        # and `createsuperuser` passes no opinion about this either way --
        # allowing one to be overridden here would only make it possible to
        # publish an administrator by accident. See `Account.is_public`.
        extra['is_public'] = False
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

    # THE JOIN KEY FOR THE IDENTITY BRIDGE, AND IT IS NOT THE EMAIL.
    #
    # §C.1: "the join key is an opaque subject id stored on the local user,
    # never an email address ... this is not a refinement, it is the thing
    # that makes the bridge sound at all". `homeschool-lms` has a non-unique
    # `User.email` -- the design document's Defect 1 -- so an instance that
    # matched entitlements on email would be matching on a field that does
    # not identify anybody.
    #
    # Opaque, so it reveals nothing if it appears in a log or a token; stable,
    # because an instance stores it against a local user and a changed value
    # would silently unlink every guardian; and `editable=False` because
    # there is no correct reason for a human to type one.
    subject = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        help_text='Opaque, stable id an installation stores to identify this '
                  'person. Never an email address.',
    )

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

    # A LOGIN AND A PUBLIC PRESENCE ARE TWO DIFFERENT THINGS.
    #
    # This model is both the marketplace identity and the Django auth user,
    # which means an operator running `createsuperuser` was, until this field
    # existed, given a page at /people/<their handle>/ announcing them as a
    # Milepost member. They had signed up for a login. Nobody involved
    # intended to publish them.
    #
    # Default False, and every ordinary door sets it True: an account that
    # arrives by a route nobody has thought about yet is private, which fails
    # in the direction of a member wondering where their page went rather
    # than somebody appearing on the site who never asked to.
    is_public = models.BooleanField(
        default=False,
        help_text=(
            'Whether this person has a page at /people/<handle>/. Set when '
            'somebody signs up; staff accounts are logins, not members.'
        ),
    )

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
        refuse_a_taken_public_name(self.handle, field='handle')

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


def refuse_a_taken_public_name(name, *, field):
    """One namespace of public names, shared by people and organisations.

    Handles and organisation slugs live at different addresses, so nothing
    technical stops `oakhill` being both a person and a co-op. What stops it
    is that attribution renders both -- "Published by oakhill, contributed by
    oakhill" -- and that a co-op is exactly the kind of thing somebody would
    register a look-alike name for. This is the same argument as
    RESERVED_HANDLES, which already refuses names that would read as coming
    from Milepost itself; a name that reads as coming from somebody else is
    the same problem with a different victim.

    A `clean()` check rather than a database constraint, because the two names
    live in different tables and no constraint spans them. So it is enforced
    wherever `full_clean` runs -- every form, and `AccountManager`, which
    calls it deliberately -- and not against a racing pair of inserts. The
    unique index on each table still stops the collision that matters most,
    which is two of the same kind.
    """
    if not name:
        return
    if field == 'handle':
        taken = Organisation.objects.filter(slug=name).exists()
    else:
        taken = Account.objects.filter(handle=name).exists()
    if taken:
        raise ValidationError({field: 'That name is already taken.'})


class Organisation(models.Model):
    """A co-op's public identity, which outlives the people who run it.

    WHY THIS EXISTS BEFORE THERE IS ANYTHING TO OWN. §C.4 of the design
    document is blunt about it: "listings need an owner that outlives any
    individual", and "the listing's owner shape is in the first migration".
    A listing owned only by whoever pressed Publish carries a departed
    organiser's name, cannot be maintained by the co-op that wrote it, and
    has no owner at all once that person deletes their account. Adding an
    alternative owner type afterwards means migrating every published listing
    and re-deciding attribution for content people are already linking to.

    So this lands before `catalog` rather than with it. There is nothing to
    publish yet, which is the point: the shape has to be right before the
    first thing depends on it.

    MINIMAL, DELIBERATELY. §C.4.6 separates what must be settled now from
    what can follow: id, slug, name and is_active are the must; a logo and a
    description are profile richness that adds a column later and breaks
    nothing. This model is the first list and stops there.
    """

    #: The same rules as a person's handle, and the same validator function --
    #: which is named `validate_handle` and stays named that, because
    #: migration 0001 references it by that path and renaming it would break
    #: a shipped migration to make a docstring read better.
    slug = models.SlugField(
        max_length=HANDLE_MAX,
        unique=True,
        validators=[validate_handle],
        help_text=(
            'The address this organisation is linked at. It must survive '
            'every membership change, so it is not something a member edits.'
        ),
    )
    name = models.CharField(
        max_length=120,
        help_text='What people see. A co-op’s name, not an abbreviation.',
    )
    # Deactivated rather than deleted, on the precedent the LMS already set
    # twice: an IntegrationToken is revoked and a Material is archived. A
    # co-op that winds down still published things, and those listings have to
    # keep an owner or they become unmaintainable and untakedownable.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # `through_fields` is required, not optional, and the reason is worth
    # keeping: OrganisationMembership has TWO foreign keys to Account --
    # `account`, who the membership is for, and `added_by`, who granted it --
    # so "the members of this organisation" is ambiguous until it is said
    # which one it means. Django refuses to guess (fields.E335), which is the
    # right call: guessing wrong here would silently list the people who
    # granted memberships as the people who hold them.
    members = models.ManyToManyField(
        'Account',
        through='OrganisationMembership',
        through_fields=('organisation', 'account'),
        related_name='organisations',
    )

    class Meta:
        ordering = ['slug']

    def __str__(self):
        return self.slug

    def clean(self):
        super().clean()
        self.slug = (self.slug or '').strip().lower()
        refuse_a_taken_public_name(self.slug, field='slug')

    def save(self, *args, **kwargs):
        self.slug = (self.slug or '').strip().lower()
        super().save(*args, **kwargs)

    @property
    def public_name(self):
        """The same property name as an Account's, and for the same reason.

        Attribution renders an owner and a contributor side by side, and the
        template should not have to know which kind of thing it is holding.
        """
        return self.name.strip() or self.slug

    def owners(self):
        return self.memberships.filter(role=OrganisationMembership.Role.OWNER)

    def can_publish(self, account):
        """Both roles may publish; only an owner may accept terms for the org.

        This is the person half of §C.4.3's two-layer check. The installation
        half -- that the machine speaking is bound to this organisation --
        belongs with `instances`, and a publish needs both.
        """
        return self.memberships.filter(account=account).exists()

    def add_member(self, account, role=None, added_by=None):
        return OrganisationMembership.objects.create(
            organisation=self,
            account=account,
            role=role or OrganisationMembership.Role.PUBLISHER,
            added_by=added_by,
        )

    def remove_member(self, account):
        """Refuses to remove the last owner.

        The precedent is `students.remove_guardian` in the LMS, which refuses
        for the same reason in a different shape: a child with no guardian is
        a record nobody can manage, and an organisation with no owner is a set
        of listings nobody can maintain or take down. Both failures are quiet
        and both are discovered by somebody who needed to act and could not.
        """
        membership = self.memberships.filter(account=account).first()
        if membership is None:
            return
        if (
            membership.role == OrganisationMembership.Role.OWNER
            and self.owners().count() == 1
        ):
            raise ValidationError(
                'An organisation must keep at least one owner. Add another '
                'before removing this one.'
            )
        membership.delete()


class OrganisationMembership(models.Model):
    """Who may act for an organisation, who granted it, and when.

    A THROUGH MODEL RATHER THAN A PLAIN MANY-TO-MANY, by the rule this
    codebase applies wherever it picks between the two: a plain M2M is right
    when there is nothing to record about the relationship beyond its
    existence, and the moment there is -- who granted it, when, with what
    remit -- it should be a through model. All three exist here.

    §C.4.6 puts the roles themselves in the "can follow" column and suggests
    starting with plain membership. They are here anyway, because the next
    model in this sequence needs them: §C.4.7's `TermsAcceptance` says a
    PUBLISHER cannot accept terms on the organisation's behalf, since
    accepting them is an ownership act. Shipping without the role means adding
    it in the very next commit, and a column added a week later is the same
    column with a migration in between.
    """

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        PUBLISHER = 'PUBLISHER', 'Publisher'

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name='memberships',
    )
    account = models.ForeignKey(
        'Account', on_delete=models.CASCADE,
        related_name='organisation_memberships',
    )
    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.PUBLISHER,
    )
    added_at = models.DateTimeField(default=timezone.now)
    # SET_NULL, not CASCADE: the fact that somebody was added to a co-op is
    # not undone by the person who added them closing their account. The same
    # reasoning governs `Listing.contributed_by` and `TermsAcceptance
    # .accepted_by` when those arrive.
    added_by = models.ForeignKey(
        'Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='memberships_granted',
    )

    class Meta:
        ordering = ['organisation', 'account']
        constraints = [
            models.UniqueConstraint(
                fields=['organisation', 'account'],
                name='one_membership_per_account_per_organisation',
            ),
        ]

    def __str__(self):
        return f'{self.account.handle} in {self.organisation.slug}'


#: How long an authorization code is good for. Deliberately short: it is a
#: one-time value handed to a browser to carry across a redirect, and the only
#: thing it has to survive is that redirect. RFC 6749 recommends a maximum of
#: ten minutes and says a code SHOULD be single-use; this is both, and one
#: minute would probably also work.
AUTHORIZATION_CODE_SECONDS = 300


class AuthorizationCode(models.Model):
    """§C.1's layer 2, in the five minutes between consent and collection.

    THE MARKETPLACE IS THE IDENTITY PROVIDER AND AN INSTALLATION IS THE CLIENT.
    §C.1 settles that, and settles why it is OAuth rather than a shared account
    created at signup: a shared account would force every instance to be online
    to onboard *anyone*, which is the wrong dependency direction for a product
    whose whole claim is that it works alone.

    WHAT IS EXCHANGED FOR IS A SUBJECT, NOT AN ACCESS TOKEN
    --------------------------------------------------------
    This is the part that will look wrong to anybody who has implemented OAuth
    before, so it is the part worth explaining.

    The textbook flow ends with the client holding a bearer token it uses to
    call APIs as the user. Nothing here would accept one. §A's seam means every
    machine-channel request is authenticated by the *installation* credential
    and names its subject as a parameter -- so a bearer token would be a
    credential with nothing to open, and issuing one would mean inventing a
    second way to authenticate the same channel. Two ways to prove the same
    thing is how one of them ends up weaker and nobody notices.

    What the instance actually needs is the one fact §C.1 names: "an opaque
    marketplace subject id" to store against its local user. So the code is
    exchanged for that, plus the `InstallationLink` that makes it usable.

    PKCE IS NOT OPTIONAL HERE EVEN THOUGH THE CLIENT HAS A SECRET
    --------------------------------------------------------------
    An installation holds a signing key, so it *could* authenticate the token
    exchange and skip the proof key. PKCE is kept because the authorization
    code travels through a browser the marketplace does not control -- a
    guardian's own -- and a code intercepted from a redirect is useless without
    the verifier. The client secret protects against a stolen code being
    redeemed by a different client; PKCE protects against it being redeemed by
    the same client's compromised redirect. They are different attacks and this
    uses both.

    SINGLE USE, AND `redeemed_at` RATHER THAN A DELETE
    ---------------------------------------------------
    A code that has been spent is deleted in many implementations, which makes
    a replayed redemption indistinguishable from an expired one and leaves no
    trace of either. Here it is marked, so a second attempt on a spent code is
    a thing that can be seen in the table rather than inferred from an absence.
    Rows are swept by age, not by use.
    """

    #: The value that travels in the redirect. Opaque and high-entropy: it is a
    #: bearer credential for the length of its life, however short that is.
    code = models.CharField(max_length=64, unique=True, editable=False)

    installation = models.ForeignKey(
        'instances.Installation', on_delete=models.CASCADE,
        related_name='authorization_codes',
    )
    account = models.ForeignKey(
        'Account', on_delete=models.CASCADE,
        related_name='authorization_codes',
    )

    #: The S256 challenge. The verifier is never stored -- storing it would
    #: make the database a place the proof key can be read from, which is the
    #: one thing PKCE exists to avoid.
    code_challenge = models.CharField(max_length=128)

    #: Recorded because RFC 6749 requires the redemption to present the same
    #: one, and because an authorization server that does not check it will
    #: happily send a code somewhere the client never asked for.
    redirect_uri = models.URLField()

    created_at = models.DateTimeField(default=timezone.now)
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'code for {self.account.handle} on {self.installation}'

    @property
    def has_expired(self):
        age = (timezone.now() - self.created_at).total_seconds()
        return age > AUTHORIZATION_CODE_SECONDS

    @property
    def is_spendable(self):
        return self.redeemed_at is None and not self.has_expired

    def verifies(self, code_verifier):
        """S256 only. `plain` is in the RFC and is not implemented.

        RFC 7636 permits a `plain` method where the challenge *is* the
        verifier, for clients that cannot compute a SHA-256. Every client here
        is a Django application, so the only thing supporting `plain` would add
        is a way to downgrade -- an attacker who can influence the challenge
        picking the method that requires no secret at all.
        """
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('ascii')).digest()
        ).rstrip(b'=').decode('ascii')
        return secrets.compare_digest(expected, self.code_challenge)
