"""Provisioning, which is the only way an installation comes into existence.

There is no registration endpoint -- see `models.Installation` for why -- so
this screen is the door. It is deliberately awkward in one specific way: the
signing key is never displayed, so an operator who needs one uses **Rotate the
signing key**, which shows it once and invalidates the old one. Looking a
credential up is the habit that puts it in a screenshot.
"""

from django.contrib import admin, messages

from .models import Installation, InstallationLink, new_secret


class InstallationLinkInline(admin.TabularInline):
    """Who this installation may speak for.

    Created here because §C.1's OAuth flow -- the thing that will eventually
    write these when a guardian links from inside their instance -- is not
    built. Until it is, a link is an operator action, which is the same
    provisioning path the installation itself takes and fails in the same safe
    direction: nothing gets onto this channel that nobody chose to put there.
    """

    model = InstallationLink
    extra = 0
    autocomplete_fields = ['account']


@admin.register(Installation)
class InstallationAdmin(admin.ModelAdmin):
    list_display = ['name', 'identifier', 'organisation', 'is_active',
                    'last_seen_at']
    list_filter = ['is_active']
    search_fields = ['name', 'identifier']
    autocomplete_fields = ['organisation']
    readonly_fields = ['identifier', 'created_at', 'last_seen_at']
    fields = ['name', 'organisation', 'is_active', 'identifier', 'created_at',
              'last_seen_at']
    inlines = [InstallationLinkInline]
    actions = ['rotate_signing_key']

    def save_model(self, request, obj, form, change):
        """A new installation gets a secret, shown once, in a message.

        `Installation.provision` is the ordinary door; this is the operator
        one. Both have to produce a usable credential, or an operator ends up
        with a row that can never authenticate and nothing saying why -- a
        blank `signing_key` would otherwise sign as the empty string and refuse
        everything.
        """
        is_new = not change
        if is_new:
            obj.signing_key = new_secret()
        super().save_model(request, obj, form, change)
        if is_new:
            messages.warning(
                request,
                f'Signing key for {obj.name}, shown once and not readable '
                f'back from any screen: {obj.signing_key}',
            )

    @admin.action(description='Rotate the signing key')
    def rotate_signing_key(self, request, queryset):
        for installation in queryset:
            secret = installation.rotate_secret()
            messages.warning(
                request,
                f'New signing key for {installation.name}, shown once: '
                f'{secret}. The previous one stopped working immediately.',
            )


@admin.register(InstallationLink)
class InstallationLinkAdmin(admin.ModelAdmin):
    list_display = ['account', 'installation', 'linked_at']
    search_fields = ['account__handle', 'installation__name']
    autocomplete_fields = ['account', 'installation']
