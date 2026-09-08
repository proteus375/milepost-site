"""Moderation, in the smallest form that is still moderation.

§A says the marketplace needs an operations surface on day one, and §D's
publishing sequence ends "moderation, then published". There is no queue here
and no review workflow: there is a status field, a filter on it, and an
operator who can move a listing between states. That is enough to take
something down, which is the one thing that cannot wait, and it is honest
about being the whole of it.

`TermsAcceptance` is registered read-only. The rows are append-only by design
-- the history of who agreed to what, when, is the entire point, and an
editable form is an invitation to destroy exactly the fact the model holds.
Deleting is allowed, because a genuinely mistaken row (a test acceptance, a
duplicate from a bug) has to be removable by somebody; editing one is never
the right repair.
"""

from django.contrib import admin

from .models import Listing, TermsAcceptance


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = [
        'slug', 'title', 'subject', 'status', 'owner_name', 'published_at',
    ]
    list_filter = ['status', 'subject']
    search_fields = ['slug', 'title', 'summary']
    autocomplete_fields = [
        'owner_account', 'owner_organisation', 'contributed_by',
    ]
    readonly_fields = ['created_at', 'updated_at', 'terms_version']
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'summary', 'description')}),
        ('Where it fits', {'fields': ('subject', 'grade_min', 'grade_max')}),
        # The three references of §C.4.2 shown together, because exactly one
        # owner is a rule an operator has to be able to see they are obeying.
        ('Attribution', {'fields': (
            'owner_account', 'owner_organisation', 'contributed_by',
        )}),
        ('Publication', {'fields': (
            'status', 'version', 'licence', 'terms_version', 'published_at',
        )}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Owner')
    def owner_name(self, listing):
        return listing.owner_name


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(admin.ModelAdmin):
    list_display = ['subject', 'terms_version', 'accepted_by', 'accepted_at']
    list_filter = ['terms_version']
    search_fields = ['account__handle', 'organisation__slug']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Accepted by')
    def subject(self, acceptance):
        return acceptance.subject
