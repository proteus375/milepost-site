"""Provisioning, which is the only way an installation comes into existence.

There is no registration endpoint -- see `models.Installation` for why -- so
this screen is the door. It is deliberately awkward in one specific way: the
signing key is never displayed on any ordinary screen, so an operator who needs
one uses **Rotate the signing key**, which shows it once and invalidates the
old one. Looking a credential up is the habit that puts it in a screenshot.

A NEW CREDENTIAL IS RENDERED, NEVER MESSAGED
----------------------------------------------
The first version used `messages.warning`, which is the obvious thing and is
wrong here. Django's default `MESSAGE_STORAGE` is `FallbackStorage`, and its
first choice is `CookieStorage` -- so a message this size goes into a COOKIE:
written to the operator's disk by their browser, sent back on every subsequent
request, and visible to anything that logs request headers.

The whole argument for the HMAC scheme in `instances/auth.py` is that the
credential never travels. Announcing one in a cookie hands that back for the
sake of a convenience. So both doors return a rendered page instead, and the
secret exists in exactly one response body.

This is the same mistake `make_licence_key` made one layer down, found by
looking for it after that one. The general form is worth keeping: **a secret
put somewhere for a human to read is a secret put somewhere.** The question is
never whether the human can be trusted; it is what else is standing between
the value and the disk.
"""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import reverse

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
    list_display = ['name', 'identifier', 'organisation', 'can_link',
                    'is_active', 'last_seen_at']
    list_filter = ['is_active']
    search_fields = ['name', 'identifier']
    autocomplete_fields = ['organisation']
    readonly_fields = ['identifier', 'created_at', 'last_seen_at']
    fields = ['name', 'organisation', 'redirect_uri', 'is_active',
              'identifier', 'created_at', 'last_seen_at']
    inlines = [InstallationLinkInline]
    actions = ['rotate_signing_key']

    def save_model(self, request, obj, form, change):
        """A new installation gets a secret. `response_add` shows it.

        `Installation.provision` is the ordinary door; this is the operator
        one. Both have to produce a usable credential, or an operator ends up
        with a row that can never authenticate and nothing saying why -- a
        blank `signing_key` would otherwise sign as the empty string and refuse
        everything.
        """
        if not change:
            obj.signing_key = new_secret()
            # Carried on the instance rather than in the session, for the
            # reason in the module docstring. `response_add` is the next thing
            # to run and the only thing that needs it.
            obj._fresh_secret = obj.signing_key
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        secret = getattr(obj, '_fresh_secret', None)
        if secret is None:
            return super().response_add(request, obj, post_url_continue)
        return self._credential_page(
            request, [(obj, secret)], 'Installation provisioned',
        )

    @admin.display(boolean=True, description='Can link accounts')
    def can_link(self, installation):
        """On the list because a blank redirect URI is invisible until a
        guardian tries to link and is refused, and the person who sees that
        refusal is not the person who can fix it."""
        return bool(installation.redirect_uri)

    @admin.action(description='Rotate the signing key')
    def rotate_signing_key(self, request, queryset):
        rotated = [(i, i.rotate_secret()) for i in queryset]
        if not rotated:
            return None
        return self._credential_page(
            request, rotated, 'Signing keys rotated', rotated=True,
        )

    def _credential_page(self, request, pairs, title, rotated=False):
        return TemplateResponse(
            request, 'admin/instances/credential.html', {
                **self.admin_site.each_context(request),
                'title': title,
                'credentials': [
                    {'installation': i, 'secret': s} for i, s in pairs
                ],
                'rotated': rotated,
                'back': reverse('admin:instances_installation_changelist'),
            },
        )


@admin.register(InstallationLink)
class InstallationLinkAdmin(admin.ModelAdmin):
    list_display = ['account', 'installation', 'linked_at']
    search_fields = ['account__handle', 'installation__name']
    autocomplete_fields = ['account', 'installation']
