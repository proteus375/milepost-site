"""Course plans people share, and the terms that let them.

WHAT IS HERE AND WHAT IS NOT
-----------------------------
A `Listing` is the record of a shared course plan: what it is, who owns it,
who contributed it, and whether anybody may see it. It does not yet carry the
pack -- the `courselms.coursepack/1` archive with the course document, its
media and its manifest. That arrives once both repositories read the format
through one shared package rather than two copies that drift, which is a
change to `homeschool-lms` as much as to this one and does not belong in the
commit that settles the owner shape.

So: a catalogue of plans with nothing to download yet. Said plainly here
because a reader finding `version` and `licence` on this model would
reasonably assume otherwise.

THE OWNER SHAPE IS THE POINT OF THIS COMMIT
--------------------------------------------
§C.4.2 of the design document, and it is three references rather than one:

    owner_account         nullable -- set for a personal listing
    owner_organisation    nullable -- set for an organisation's listing
    contributed_by        the account that actually pressed Publish

with a database constraint that exactly one owner is set. Ownership is what
survives; `contributed_by` is the historical fact of who did the work, and it
is recorded whichever owner applies. Attribution renders both -- "Published by
Oak Hill Co-op, contributed by Priya" -- so the individual keeps visible
credit while the organisation holds the listing. When Priya leaves, nothing
about the listing changes, because nothing about it was ever hers.

§C.4.5 is why this is not deferred: adding an alternative owner type
afterwards means migrating every published listing and re-deciding
attribution for content people are already linking to.

THE TERMS ARE DRAFTS, AND THE CODE SHOULD NOT PRETEND OTHERWISE
----------------------------------------------------------------
`legal/publisher-terms.md` is version 1.0 and says at the top: "DRAFT -- not
reviewed by counsel. Do not publish or rely on this document." The constants
below name that version because recording *which* version somebody accepted
is the whole mechanism, and a placeholder would make the first real
acceptances unattributable. Nothing is deployed, so nobody has accepted
anything; when counsel returns the reviewed text, the version it carries is
the one that goes here.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Account, Organisation, OrganisationMembership
from billing.models import household_of

from .packs import pack_path

#: The publisher terms in force. Version-stamped rather than a boolean,
#: because §C.4.7 is explicit that what has to be stored is "not a boolean but
#: which version was accepted, by whom, and when" -- terms change, and a
#: warranty nobody recorded accepting is not a warranty.
PUBLISHER_TERMS_VERSION = '1.0'

#: One platform licence, versioned, no menu (§4.4.1). Every pack carries this
#: same string; a listing records it rather than choosing it, so that a
#: downloader's perpetual licence (§4.4.3) is to a specific version of a
#: document that can be produced later.
CONTENT_LICENCE = 'milepost-1.0'

#: Kindergarten through twelfth, with K as 0 so the range is orderable and a
#: query for "suits a nine-year-old" is a comparison rather than a lookup
#: table. Rendered by `grade_label`; never shown as the integer.
GRADE_MIN = 0
GRADE_MAX = 12


def grade_label(value):
    return 'K' if value == 0 else str(value)


#: Titles that would slugify into an address `catalog/urls.py` already uses.
#: The same class of collision RESERVED_HANDLES exists for, at a different
#: level of the path. `plans/new/` is declared before `plans/<slug>/` and
#: therefore wins, so a plan called "New" would not shadow it today -- but
#: relying on declaration order means the day somebody reorders that list for
#: tidiness, it does.
RESERVED_SLUGS = frozenset({'new', 'yours', 'edit', 'publish'})


def slug_for(title):
    return slugify(title)[:80].strip('-')


def unique_slug(title):
    """Suffixes a taken slug rather than refusing.

    `portability.unique_code` in the LMS does the same thing for course codes
    and for the same reason: two people may reasonably name a plan "A Year of
    Botany", and telling the second one their title is taken is a worse answer
    than giving them botany-2.

    HERE RATHER THAN ON THE FORM, WHICH IS WHERE IT STARTED. A plan can now
    arrive two ways -- a person filling in the web form, and an instance
    pushing over §D's machine channel -- and a slug rule that lives on the form
    is a slug rule the second door does not obey. Two implementations of
    "what address does this title get" is the shape that produces a collision
    nobody can reproduce.
    """
    base = slug_for(title) or 'plan'
    slug, suffix = base, 1
    while Listing.objects.filter(slug=slug).exists():
        suffix += 1
        tail = f'-{suffix}'
        slug = f'{base[:80 - len(tail)]}{tail}'
    return slug


class Subject(models.TextChoices):
    """Broad enough that nobody has to argue, narrow enough to browse by.

    Not a taxonomy and not tags. A homeschooling parent looking for a science
    course wants one list, and a list long enough to need its own search has
    stopped being a way to find things.
    """

    LANGUAGE_ARTS = 'LANGUAGE_ARTS', 'Language arts'
    MATHEMATICS = 'MATHEMATICS', 'Mathematics'
    SCIENCE = 'SCIENCE', 'Science'
    HISTORY = 'HISTORY', 'History and social studies'
    LANGUAGES = 'LANGUAGES', 'World languages'
    ARTS = 'ARTS', 'Art and music'
    HEALTH = 'HEALTH', 'Health and physical education'
    COMPUTING = 'COMPUTING', 'Computing'
    RELIGION = 'RELIGION', 'Religious studies'
    LIFE_SKILLS = 'LIFE_SKILLS', 'Life skills'
    OTHER = 'OTHER', 'Other'


class TermsAcceptance(models.Model):
    """Who accepted which version of the publisher terms, and when.

    DELIBERATELY THE SAME SHAPE AS A LISTING'S OWNER (§C.4.7): two nullable
    subject references with exactly one set, plus a not-null record of the
    person who acted. The parallel is not decoration. The question "who is
    answerable for this listing" and the question "who accepted the terms that
    make them answerable" have to have the same possible answers, or there
    will be listings whose owner never agreed to anything. Reusing the shape
    makes that impossible rather than merely unlikely.

    APPEND-ONLY. A new terms version does not update the old row; it adds one.
    The history of who agreed to what, when, is the entire point, and an
    UPDATE would destroy exactly the fact this model exists to hold. Nothing
    here offers a way to edit one, and the admin registers it read-only.
    """

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, null=True, blank=True,
        related_name='terms_acceptances',
    )
    # PROTECT rather than CASCADE, for the same reason `Listing
    # .owner_organisation` uses it: an organisation is deactivated, never
    # deleted, precisely so that what it published and what it agreed to
    # outlive it winding down.
    organisation = models.ForeignKey(
        'accounts.Organisation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='terms_acceptances',
    )
    # SET_NULL, as `contributed_by` does below. The fact that an organisation
    # accepted the terms is not undone by the owner who clicked closing their
    # account -- the organisation accepted, and it still exists.
    accepted_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='terms_accepted_for_others',
    )
    terms_version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-accepted_at']
        constraints = [
            models.CheckConstraint(
                name='terms_acceptance_has_exactly_one_subject',
                condition=(
                    models.Q(account__isnull=False, organisation__isnull=True)
                    | models.Q(account__isnull=True, organisation__isnull=False)
                ),
            ),
            # A version is accepted once per subject. Append-only means new
            # versions add rows, not that the same one may be recorded twice
            # -- and a duplicate would make "when did they accept 1.0" a
            # question with more than one answer.
            models.UniqueConstraint(
                fields=['account', 'terms_version'],
                condition=models.Q(account__isnull=False),
                name='one_acceptance_per_account_per_version',
            ),
            models.UniqueConstraint(
                fields=['organisation', 'terms_version'],
                condition=models.Q(organisation__isnull=False),
                name='one_acceptance_per_organisation_per_version',
            ),
        ]

    def __str__(self):
        return f'{self.subject} accepted {self.terms_version}'

    @property
    def subject(self):
        """The account or organisation that accepted. Never None."""
        return self.account if self.account_id else self.organisation


def has_accepted(subject, version=PUBLISHER_TERMS_VERSION):
    """Whether this account or organisation has accepted that version."""
    field = 'account' if isinstance(subject, Account) else 'organisation'
    return TermsAcceptance.objects.filter(
        **{field: subject}, terms_version=version,
    ).exists()


def accept_terms(subject, *, accepted_by, version=PUBLISHER_TERMS_VERSION):
    """Record an acceptance, refusing the two ways it can be meaningless.

    A PUBLISHER cannot accept on an organisation's behalf. That is not a
    convenience check -- `legal/publisher-terms.md` says it in the document
    people are agreeing to ("An organisation accepts through one of its
    owners"), and §C.4.1 draws the same line, because accepting terms is an
    ownership act rather than a publishing one.
    """
    if isinstance(subject, Account):
        if subject != accepted_by:
            raise ValidationError(
                'Nobody can accept the publisher terms for somebody else.'
            )
        return TermsAcceptance.objects.get_or_create(
            account=subject, terms_version=version,
            defaults={'accepted_by': accepted_by},
        )[0]

    if not isinstance(subject, Organisation):
        raise ValidationError('Only a person or an organisation accepts terms.')

    is_owner = subject.memberships.filter(
        account=accepted_by, role=OrganisationMembership.Role.OWNER,
    ).exists()
    if not is_owner:
        raise ValidationError(
            'Only an owner of this organisation can accept the publisher '
            'terms on its behalf.'
        )
    return TermsAcceptance.objects.get_or_create(
        organisation=subject, terms_version=version,
        defaults={'accepted_by': accepted_by},
    )[0]


class ListingQuerySet(models.QuerySet):
    def visible(self):
        """What a stranger may see. The one place that decides it."""
        return self.filter(status=Listing.Status.PUBLISHED)


class Listing(models.Model):
    """A course plan somebody shared.

    The status ladder is DRAFT -> IN_REVIEW -> PUBLISHED, with WITHDRAWN as
    the way back out, and it is the design's own sequence: an instance
    "stores it as a draft listing", the marketplace re-validates, "moderation,
    then published". Withdrawn rather than deleted, because a takedown has to
    leave the row that says a takedown happened -- and because a downloader's
    licence is perpetual, so the listing disappearing is not the same event as
    the content disappearing.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        IN_REVIEW = 'IN_REVIEW', 'In review'
        PUBLISHED = 'PUBLISHED', 'Published'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'

    title = models.CharField(max_length=150)
    slug = models.SlugField(
        max_length=80, unique=True,
        help_text='The address this plan is linked at. It does not change.',
    )
    summary = models.CharField(
        max_length=300,
        help_text='One or two sentences, shown in the list of plans.',
    )
    description = models.TextField(
        blank=True,
        help_text='What the plan covers, who it suits, what it assumes.',
    )
    subject = models.CharField(max_length=20, choices=Subject.choices)
    grade_min = models.PositiveSmallIntegerField(default=GRADE_MIN)
    grade_max = models.PositiveSmallIntegerField(default=GRADE_MAX)

    # --- the owner shape, §C.4.2 -------------------------------------------
    # CASCADE for a person: §C.4 lists "if that individual deletes their
    # marketplace account, the listings have no owner" as the decisive problem
    # organisations solve, so the honest behaviour for a listing that has no
    # organisation behind it is that it goes with them. PROTECT for an
    # organisation, because `is_active` exists so that one is deactivated
    # rather than deleted, and this makes that rule enforceable rather than
    # merely written down.
    owner_account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, null=True, blank=True,
        related_name='listings',
    )
    owner_organisation = models.ForeignKey(
        'accounts.Organisation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='listings',
    )
    # §C.4.2 calls this "not null", and §C.4.4 says it goes SET_NULL when the
    # account is deleted. Both cannot hold, and the second is the one with a
    # scenario behind it: the row must survive somebody leaving. So it is
    # nullable in the database and always set at publication -- `publish`
    # below is the only thing that sets a listing live, and it records the
    # contributor as it does.
    contributed_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contributions',
    )

    # --- the pack, and what it turned out to contain ----------------------
    # Validated by `catalog.packs` before it is written, so a listing never
    # holds an archive nobody has opened. Blank until somebody uploads one:
    # a plan can be described before it is delivered, which is the state
    # every listing starts in.
    pack = models.FileField(upload_to=pack_path, blank=True)
    pack_sha256 = models.CharField(max_length=64, blank=True)
    pack_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    pack_uploaded_at = models.DateTimeField(null=True, blank=True)
    # WHAT THE PACK CLAIMED, NOT WHAT IS TRUE. A manifest names an owner, and
    # that name is written by whoever built the archive. The listing's owner
    # is the one this site established when somebody signed in; verifying that
    # the manifest's identity really is linked to the installation that sent
    # it is §D's step 4, and it needs a machine channel that does not exist.
    # Kept because provenance somebody asserted is still evidence.
    pack_manifest = models.JSONField(null=True, blank=True)

    # STORED RATHER THAN COMPUTED. Reopening a zip to render a page would put
    # an archive parse on the path of every anonymous page view, which is a
    # denial of service somebody else gets to schedule.
    pack_course_name = models.CharField(max_length=200, blank=True)
    pack_module_count = models.PositiveIntegerField(default=0)
    pack_page_count = models.PositiveIntegerField(default=0)
    pack_media_count = models.PositiveIntegerField(default=0)

    version = models.CharField(max_length=20, default='1')
    licence = models.CharField(max_length=40, default=CONTENT_LICENCE)
    terms_version = models.CharField(
        max_length=20, blank=True,
        help_text=(
            'The publisher terms in force when this was published. Blank '
            'until it is.'
        ),
    )

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ['-published_at', '-created_at']
        constraints = [
            models.CheckConstraint(
                name='listing_has_exactly_one_owner',
                condition=(
                    models.Q(owner_account__isnull=False,
                             owner_organisation__isnull=True)
                    | models.Q(owner_account__isnull=True,
                               owner_organisation__isnull=False)
                ),
            ),
            models.CheckConstraint(
                name='listing_grade_range_is_a_range',
                condition=models.Q(grade_min__lte=models.F('grade_max')),
            ),
        ]

    def __str__(self):
        return self.slug

    def get_absolute_url(self):
        return reverse('listing', args=[self.slug])

    @property
    def owner(self):
        """The Account or Organisation that holds this. Never None."""
        return self.owner_account if self.owner_account_id else self.owner_organisation

    @property
    def owner_name(self):
        """Both kinds of owner answer to `public_name`, which is why they do."""
        return self.owner.public_name

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def has_pack(self):
        return bool(self.pack)

    @property
    def pack_contents(self):
        """What is in the pack, in a sentence, or None.

        Reads the stored counts. Nothing here opens the archive -- see the
        note on those fields.
        """
        if not self.has_pack:
            return None
        parts = [
            f'{self.pack_module_count} section' + ('' if self.pack_module_count == 1 else 's'),
            f'{self.pack_page_count} page' + ('' if self.pack_page_count == 1 else 's'),
        ]
        if self.pack_media_count:
            parts.append(
                f'{self.pack_media_count} image' + ('' if self.pack_media_count == 1 else 's')
            )
        return ', '.join(parts)

    @property
    def grade_range(self):
        if self.grade_min == self.grade_max:
            return f'Grade {grade_label(self.grade_min)}'
        return f'Grades {grade_label(self.grade_min)}–{grade_label(self.grade_max)}'

    @property
    def average_rating(self):
        """None until somebody has said something.

        A single review is not an average and showing "5.0" for one opinion
        overstates it, but hiding it entirely hides the only thing anybody has
        said. So the number is real from the first review and the count is
        always beside it -- the count is what makes the number readable.
        """
        result = self.reviews.aggregate(models.Avg('rating'))['rating__avg']
        return round(result, 1) if result is not None else None

    def may_be_edited_by(self, user):
        """Whoever could change this listing. Not a permission of its own.

        A published listing is readable by everybody, so `may_be_read_by`
        stops answering "is this yours" the moment it goes live -- which is
        exactly when it starts to matter, because that is when reviews and
        downloads begin.
        """
        if not getattr(user, 'is_authenticated', False):
            return False
        if self.owner_account_id:
            return self.owner_account_id == user.pk
        return self.owner_organisation.can_publish(user)

    def may_be_read_by(self, user):
        """Published plans are public; an unpublished one is its owner's.

        A stranger asking for an unpublished plan gets a 404 rather than a
        403, on the reasoning already written in `accounts.views.profile`:
        whether a given address belongs to anything is not something a
        stranger is owed. That decision lives in the view; this answers the
        question it asks.
        """
        if self.is_published:
            return True
        if not getattr(user, 'is_authenticated', False):
            return False
        if self.owner_account_id:
            return self.owner_account_id == user.pk
        return self.owner_organisation.can_publish(user)

    def publish(self, by):
        """Take a listing live, refusing every way that could be wrong.

        The checks are §D's step 4 and §C.4.3's person layer, minus the
        installation half -- there is no machine channel yet, so there is no
        installation to verify. When `instances` arrives, a publish will need
        both: the installation bound to the organisation, and the account a
        member of it. The two failures are different and should stay so; a
        member publishing from an unbound installation is a misconfigured
        deployment, a non-member from a bound one is a permissions error.
        """
        if self.owner_organisation_id:
            organisation = self.owner_organisation
            if not organisation.is_active:
                raise ValidationError(
                    'That organisation is closed and cannot publish.'
                )
            if not organisation.can_publish(by):
                raise ValidationError(
                    'You are not a member of that organisation.'
                )
            if not has_accepted(organisation):
                raise ValidationError(
                    'This organisation has not accepted the current '
                    'publisher terms. An owner has to accept them first.'
                )
        elif self.owner_account_id != by.pk:
            raise ValidationError('That plan is not yours to publish.')

        if not has_accepted(by):
            raise ValidationError(
                'You have not accepted the current publisher terms.'
            )

        self.contributed_by = by
        self.terms_version = PUBLISHER_TERMS_VERSION
        self.status = self.Status.PUBLISHED
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=[
            'contributed_by', 'terms_version', 'status', 'published_at',
            'updated_at',
        ])
        return self


class Acquisition(models.Model):
    """The record that an account got a specific pack.

    THE WHOLE ANTI-ABUSE STORY RESTS ON THIS ROW. §5 of the design document
    defers the review system but leaves two constraints, and this is both of
    them: "reputation and points attach to the person or organisation layer,
    never the installation", and "sockpuppet resistance and entitlement
    integrity are the same problem wearing two hats".

    A review requires one of these. That makes farming reputation cost what
    acquiring the material costs -- a subscription, per household -- rather
    than costing an afternoon of throwaway accounts. It is the difference
    between a rating that means something and a number.

    IT CANNOT BE ADDED AFTERWARDS, which is why it is here before anything can
    be downloaded. Reviews written before this model existed would have no
    acquisition behind them, and there is no way to establish one later: the
    download already happened, unrecorded. The same argument that put
    `TermsAcceptance` in catalog's first migration.

    `pack_sha256` records WHICH pack they got, not just that they got one. A
    listing can be revised, and somebody who acquired version 1 is entitled to
    review version 1 -- the review says so, and a later version does not
    inherit it.
    """

    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, related_name='acquisitions',
    )
    # DENORMALISED AT WRITE TIME, AND THAT IS THE HONEST SHAPE RATHER THAN A
    # SHORTCUT. §H.6 settles that a family counts once however many
    # marketplace identities it links, so `WIDELY_USED` counts DISTINCT
    # household -- and a UniqueConstraint cannot span a join, so the column
    # has to be here rather than resolved through `account`.
    #
    # Resolving it live would also be wrong, not merely slower. People move
    # between households -- a separated couple becomes two -- and the
    # household that took a copy is a fact about the day it happened. A
    # membership change must not retroactively re-attribute a download to a
    # household that never made it.
    #
    # PROTECT, because a household is deactivated rather than deleted
    # (`billing.models`, and the same rule `Listing.owner_organisation`
    # follows): §4.4.3 makes a download licence perpetual, so the row saying
    # who holds one has to outlive the subscription that bought it.
    household = models.ForeignKey(
        'billing.Household', on_delete=models.PROTECT,
        related_name='acquisitions',
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name='acquisitions',
    )
    #: The pack as it was when they took it. Blank only if a listing somehow
    #: had none, which `download_pack` refuses.
    pack_sha256 = models.CharField(max_length=64, blank=True)
    version = models.CharField(max_length=20, blank=True)
    acquired_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-acquired_at']
        constraints = [
            # One per person per listing. §4.4.3 makes a download licence
            # perpetual once acquired, so a second download is the same
            # acquisition happening again rather than a new one -- and two
            # rows would make "when did they get it" a question with two
            # answers.
            models.UniqueConstraint(
                fields=['account', 'listing'],
                name='one_acquisition_per_account_per_listing',
            ),
        ]

    def __str__(self):
        return f'{self.account.handle} has {self.listing.slug}'


def record_acquisition(listing, account):
    """Note that this account has the pack. Idempotent.

    Called when a download succeeds. Deliberately NOT called for somebody who
    could publish the listing anyway: an author holding their own work is not
    an acquisition, they cannot review it, and a row saying otherwise would be
    the first lie in the table reputation is computed from.

    RAISES rather than returning None when there is no household, and the
    difference between the two exits matters. Returning None means "correctly
    nothing to record" -- an author holding their own work. An account with no
    household reaching here means the entitlement gate upstream did not run,
    which is a bug that would otherwise present as downloads that silently
    never count. `download_pack` refuses first; this is the assertion that it
    did.
    """
    if listing.may_be_edited_by(account):
        return None
    household = household_of(account)
    if household is None:
        raise ValidationError(
            'A download cannot be recorded for an account with no household. '
            'Entitlement is checked before the bytes go out.'
        )
    return Acquisition.objects.get_or_create(
        account=account, listing=listing,
        defaults={
            'household': household,
            'pack_sha256': listing.pack_sha256,
            'version': listing.version,
        },
    )[0]


class Review(models.Model):
    """One person's account of using a plan.

    Requires an `Acquisition`, refuses your own listing, and one per person
    per listing. The rating is a number because reputation and sorting need
    one; the prose is what another parent actually reads.

    NOT append-only, unlike `TermsAcceptance`, and the difference is who the
    row belongs to. An acceptance is evidence about somebody's agreement and
    editing it would destroy the fact it holds. A review is its author's own
    words about their own experience, and somebody who used a plan for a term
    and changed their mind should be able to say so.

    `version_reviewed` stamps which version this was about. A publisher who
    revises a pack does not inherit praise for a different one, and a reader
    can see that a five-star review predates the rewrite.
    """

    class Rating(models.IntegerChoices):
        POOR = 1, 'Would not use again'
        FAIR = 2, 'Some of it worked'
        GOOD = 3, 'Worth using'
        STRONG = 4, 'Would recommend'
        EXCELLENT = 5, 'Would use again with another child'

    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name='reviews',
    )
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE, related_name='reviews',
    )
    # TAKEN FROM THE ACQUISITION, NOT LOOKED UP AFRESH. A review stands on a
    # copy somebody took, and the household that took that copy is the
    # household whose opinion this is. Re-resolving it at review time would
    # let a person who changed households in between carry the opinion to the
    # new one, which is both wrong as a record and the exact move the
    # constraint below exists to refuse.
    household = models.ForeignKey(
        'billing.Household', on_delete=models.PROTECT, related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(choices=Rating.choices)
    body = models.TextField(
        blank=True,
        help_text='What worked, what you would change, who it suited.',
    )
    #: The listing version this review is about, copied at the time.
    version_reviewed = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'listing'],
                name='one_review_per_account_per_listing',
            ),
            # §H.6. A rating is one household's experience of a plan, and two
            # parents on one subscription who both liked it have one
            # experience between them -- counting it twice overstates it
            # whether or not anybody meant to. The honest rule and the
            # anti-abuse rule turn out to be the same rule, which is the shape
            # §5 predicted when it said sockpuppet resistance and entitlement
            # integrity were one problem.
            #
            # BOTH CONSTRAINTS, NOT JUST THIS ONE. The account rule is not
            # implied by the household rule: somebody who moves to a second
            # household could otherwise review the same listing again, from
            # the new one. Two cheap indexes beat reasoning about that.
            models.UniqueConstraint(
                fields=['household', 'listing'],
                name='one_review_per_household_per_listing',
            ),
        ]

    def __str__(self):
        return f'{self.account.handle} on {self.listing.slug}'

    @property
    def was_edited(self):
        """Shown to readers. A review that changed after people read it is a
        different statement, and hiding that is a small dishonesty."""
        return (self.updated_at - self.created_at).total_seconds() > 60

    @property
    def is_of_an_older_version(self):
        return bool(self.version_reviewed) and self.version_reviewed != self.listing.version


def acquisition_for(listing, account):
    """The row this person's review would stand on, or None."""
    if not getattr(account, 'is_authenticated', False):
        return None
    return Acquisition.objects.filter(
        listing=listing, account=account,
    ).select_related('household').first()


def may_review(listing, account):
    """Whether this account is allowed to review this listing, and why not.

    Returns None when they may, or a sentence when they may not -- a sentence
    rather than False because every one of these refusals is something the
    person should be told, and a bare boolean at the call site turns into a
    generic message that explains nothing.
    """
    if not getattr(account, 'is_authenticated', False):
        return 'Only people with a Milepost account can review a plan.'
    if not listing.is_published:
        return 'This plan is not published yet.'
    if listing.may_be_edited_by(account):
        return 'You cannot review a plan you publish.'

    acquisition = acquisition_for(listing, account)
    if acquisition is None:
        return (
            'Reviews come from people who have used the plan, so this needs '
            'a copy of the pack first.'
        )

    # §H.6, and the refusal has to name the household or it reads as a bug.
    # Somebody told "you have already reviewed this" who knows perfectly well
    # they have not will assume the site is broken rather than that their
    # partner got there first.
    taken = Review.objects.filter(
        listing=listing, household=acquisition.household,
    ).exclude(account=account).exists()
    if taken:
        return (
            'Somebody on your household has already reviewed this plan. A '
            'plan gets one review per household, and they can edit theirs.'
        )
    return None
