"""The operator surface for entitlement, which is the whole of billing today.

`entitled_through` is editable here on purpose and will stay editable after
Stripe writes it. §A names the admin as one of the two reasons this project is
Django at all, and an operator who cannot extend a household by a week after a
failed payment they have already sorted out on the phone has to fix it in a
shell. A support action taken in `manage.py shell` leaves no record that
anybody took it; taken here, it does.

`is_entitled` is shown read-only beside the date because the date alone does
not answer the question an operator arrived with -- a deactivated household
with a future date is not entitled, and reading that off two fields is exactly
the arithmetic a support call gets wrong.
"""

from django.contrib import admin

from .models import Household, HouseholdMembership


class HouseholdMembershipInline(admin.TabularInline):
    """Membership is edited from the household, on the precedent
    `MembershipInline` set for organisations: the question an operator
    arrives with is "who is on this subscription", and an inline answers it
    in one screen.

    `add_member`'s refusals do not run here -- an inline writes rows
    directly -- and that is deliberate rather than overlooked. The admin is
    the recovery path for when the service layer has already refused
    something that genuinely has to happen, which is the same reason
    `Organisation.remove_member` is not enforced here either. The one rule
    that does still hold is `one_household_per_account`, because it is a
    database constraint rather than a method, and an operator who tries to
    put somebody on a second household gets an IntegrityError rather than a
    quiet second subscription.
    """

    model = HouseholdMembership
    extra = 0
    autocomplete_fields = ['account', 'added_by']


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'entitled_through', 'is_entitled', 'is_active',
                    'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'members__handle', 'members__email']
    inlines = [HouseholdMembershipInline]
    fields = ['name', 'entitled_through', 'is_entitled', 'is_active',
              'created_at']
    readonly_fields = ['is_entitled', 'created_at']

    @admin.display(boolean=True, description='Entitled today')
    def is_entitled(self, household):
        return household.is_entitled
