"""The operations surface §A says a marketplace needs on day one.

Deliberately thin for now: an account has almost nothing on it, and the
moderation queue this will grow into belongs with `catalog`, where the things
being moderated live.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Account, Organisation, OrganisationMembership


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
