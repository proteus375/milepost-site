"""The operations surface §A says a marketplace needs on day one.

Deliberately thin for now: an account has almost nothing on it, and the
moderation queue this will grow into belongs with `catalog`, where the things
being moderated live.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Account


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
