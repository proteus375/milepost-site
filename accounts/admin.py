"""The operations surface §A says a marketplace needs on day one.

Still thin: an account has almost nothing on it, and the moderation queue this
will grow into belongs with `catalog`, where the things being moderated live.

`Award` is here because this is where it lives, and it is the one registration
that is neither read-only nor freely editable -- see `AwardAdmin`.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Account, Award, Organisation, OrganisationMembership


@admin.register(Account)
class AccountAdmin(UserAdmin):
    ordering = ['handle']
    list_display = [
        'handle', 'email', 'display_name', 'date_joined', 'is_active',
        'is_public',
    ]
    search_fields = ['handle', 'email', 'display_name']
    # `handle` is editable here and not by the person themselves, on purpose:
    # support fixing a typo is a different act from somebody quietly vacating
    # an address other people have linked to. See ProfileForm.
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        # `is_public` sits with the identity rather than with the
        # permissions, because it is not one: it says whether there is a
        # page at /people/<handle>/, not what this person may do.
        ('Public identity', {
            'fields': ('handle', 'display_name', 'is_public'),
        }),
        ('Terms', {'fields': ('terms_accepted_at',)}),
        ('Permissions', {'fields': (
            'is_active', 'is_staff', 'is_superuser', 'groups',
            'user_permissions',
        )}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'handle', 'password1', 'password2'),
        }),
    )


class MembershipInline(admin.TabularInline):
    """Membership is edited from the organisation, not the other way round.

    The question an operator arrives with is "who can act for this co-op",
    and an inline on the organisation answers it in one screen. `added_by` is
    shown and left editable: it is a historical fact, and the admin is the
    recovery path for when the service layer has already refused something
    that genuinely has to happen. See `Organisation.remove_member`.
    """

    model = OrganisationMembership
    extra = 0
    autocomplete_fields = ['account', 'added_by']


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    ordering = ['slug']
    list_display = ['slug', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['slug', 'name']
    inlines = [MembershipInline]
    # `slug` is editable here and nowhere else, on the same reasoning as
    # `handle` above: support fixing a typo is a different act from an
    # organisation quietly vacating an address other people have linked to.
    fields = ['slug', 'name', 'is_active', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    """The one registration in this project that is neither read-only nor open.

    `TermsAcceptance` is read-only because it is evidence about somebody
    else's act. `Award` is the platform's OWN statement, and §H.3 asks for a
    narrower thing: **`revoked_at` editable, everything else read-only.** An
    operator has to be able to withdraw a badge -- that is the whole reason
    revocation exists -- and must not be able to quietly rewrite what a badge
    was granted for, because the reason is the evidence of what Milepost
    vouched for.

    ADDABLE, UNLIKE `TermsAcceptance` AND `Acquisition`, and for one named
    reason: `FOUNDING` is "staff judgement, early contributors" (§H.4). It is
    the only badge with no rule behind it, so this form is the only way it can
    ever be granted. Every other kind is reachable from here too, which is
    deliberate -- a rule that failed to fire is a Saturday problem, and an
    operator who can only wait for the next periodic pass cannot fix it.

    NOT DELETABLE. `TermsAcceptance` and `Acquisition` both allow deletion so
    that a genuinely mistaken row can be removed, and that reasoning does not
    carry here: a mistaken award has a repair of its own, which is to revoke
    it with the reason "granted in error". Deleting one would destroy the only
    record that Milepost ever made the claim, which is exactly what §H.3's
    "revoked, never deleted" is for. The two rules would contradict each other
    if this form offered a delete button.
    """

    list_display = ['subject', 'kind', 'listing', 'awarded_at', 'awarded_by',
                    'revoked_at']
    list_filter = ['kind', 'revoked_at', 'awarded_at']
    search_fields = [
        'account__handle', 'organisation__slug', 'listing__slug', 'reason',
    ]
    autocomplete_fields = [
        'account', 'organisation', 'listing', 'awarded_by',
    ]
    fieldsets = (
        # The two subject references shown together, because exactly one of
        # them is a rule an operator has to be able to see they are obeying --
        # the same reason `ListingAdmin` groups its three.
        ('Who it is about', {'fields': ('account', 'organisation')}),
        ('What it is', {'fields': ('kind', 'listing', 'reason')}),
        ('Granted', {'fields': ('awarded_at', 'awarded_by')}),
        ('Withdrawn', {'fields': ('revoked_at', 'revoked_reason')}),
    )

    def get_readonly_fields(self, request, obj=None):
        """Everything but the revocation, once the row exists.

        COMPUTED RATHER THAN DECLARED, and that is not style. A `readonly_fields`
        list is applied to the add form too, and the admin renders a read-only
        field by evaluating it against a throwaway unsaved instance -- which is
        how `InstallationAdmin` came to display an identifier that was never
        the one saved. An add form with nothing editable on it would be worse
        still: it would silently refuse to record the one badge that has no
        rule to grant it.
        """
        if obj is None:
            return []
        return [
            'account', 'organisation', 'kind', 'listing', 'reason',
            'awarded_at', 'awarded_by',
        ]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Subject')
    def subject(self, award):
        return award.subject

