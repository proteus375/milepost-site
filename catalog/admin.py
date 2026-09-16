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
from django.template.response import TemplateResponse
from django.urls import path

from . import brigading
from .models import Acquisition, Listing, Review, TermsAcceptance


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


@admin.register(Acquisition)
class AcquisitionAdmin(admin.ModelAdmin):
    """Read-only, because these are not opinions -- they are the record of
    what happened, and the thing every review stands on. An operator who can
    hand somebody an acquisition can hand somebody the right to review a plan
    they never used, which is the abuse this model exists to prevent.

    Deletable, because a genuinely mistaken row has to be removable by
    somebody. Editable, never.
    """

    # `household` is on the list because it is what anything counting these
    # rows counts (§H.6), and a column an operator cannot see is a column
    # they cannot sanity-check. It is also half of §H.7's brigading query --
    # a cluster of first-time acquisitions of one listing in a short window
    # reads very differently when they are all one household.
    list_display = ['account', 'household', 'listing', 'version', 'acquired_at']
    list_filter = ['acquired_at']
    search_fields = ['account__handle', 'listing__slug', 'household__name']
    autocomplete_fields = ['account', 'listing', 'household']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Moderation, in the smallest form that is still moderation: an operator
    can read reviews and take one down. Not edit one -- a review is somebody
    else's words under their own name, and changing them is worse than
    removing them.
    """

    list_display = ['account', 'household', 'listing', 'rating',
                    'version_reviewed', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['account__handle', 'listing__slug', 'body']
    autocomplete_fields = ['account', 'listing']
    readonly_fields = [
        'account', 'household', 'listing', 'rating', 'body',
        'version_reviewed', 'created_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        return False

    # --- §H.7's brigading query -------------------------------------------
    #
    # A PAGE, NOT A RULE. §H.7 refuses an automatic threshold for three
    # reasons, and the third is the one that shapes this: "a suppression rule
    # is invisible to the person it acts on and produces a support
    # conversation nobody in it can win." So this reads and displays; nothing
    # here writes, hides, or discounts anything.
    #
    # ON `ReviewAdmin` RATHER THAN `ListingAdmin`, though it lists listings.
    # What an operator arrives with is a suspicion about reviews, and the
    # thing they will do next is open them -- `AcquisitionAdmin`'s note about
    # `household` being "half of §H.7's brigading query" points the same way.
    #
    # DISCOVERABLE, because a moderation tool nobody can find is not one. The
    # link is in `admin/catalog/review/change_list.html`, which Django picks
    # up by name with no `change_list_template` to set.

    def get_urls(self):
        """The custom view first, so the default `<path:object_id>/` catch-all
        does not swallow `brigading/` and send somebody to a 404 for a review
        with that primary key."""
        return [
            path(
                'brigading/',
                self.admin_site.admin_view(self.brigading_view),
                name='catalog_review_brigading',
            ),
        ] + super().get_urls()

    def brigading_view(self, request):
        """The clusters, with the thresholds that produced them on the page.

        The numbers are rendered rather than left in the source because
        whoever reads this page is the person best placed to say they are
        wrong, and they cannot say so about a threshold they cannot see.
        """
        return TemplateResponse(
            request,
            'admin/catalog/review/brigading.html',
            {
                **self.admin_site.each_context(request),
                'title': 'Possible brigading',
                'clusters': brigading.clusters(),
                'window_days': brigading.WINDOW.days,
                'minimum': brigading.CLUSTER_MINIMUM,
                'poor_at_or_below': brigading.POOR,
                'mostly_poor': int(brigading.MOSTLY_POOR * 100),
                'opts': self.model._meta,
            },
        )
