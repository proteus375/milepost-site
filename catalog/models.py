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

from accounts.models import Account, Organisation, OrganisationMembership

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
