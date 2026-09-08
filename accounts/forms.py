"""Signing up and editing a profile.

The rules a handle has to meet live on the model as a validator, not here --
see `accounts.models.validate_handle`. A form is one way in; the admin and a
future OAuth-driven signup are others, and a rule enforced by whichever form
somebody happened to use is a rule that lasts until the second door is built.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import Account


class SignUpForm(UserCreationForm):
    """Email, handle, password, and a confirmation that this is an adult.

    THE CONFIRMATION IS NOT AN AGE FIELD, and the difference is the point. It
    records that somebody said yes on a date -- which is all anybody ever
    needs to know -- rather than storing how old they are, which this product
    has no use for and, for a minor, must not hold at all. See the module
    docstring in models.py and §4.4.7 of the design document.
    """

    confirms_adult = forms.BooleanField(
        required=True,
        label='I am 18 or older and accept the terms',
        help_text=(
            'Milepost accounts are for adults. Children use their family’s '
            'own copy of Milepost and never need an account here.'
        ),
        error_messages={
            'required': (
                'Milepost accounts are for adults, so this one has to be '
                'ticked.'
            ),
        },
    )

    class Meta:
        model = Account
        fields = ['email', 'handle', 'display_name']
        labels = {
            'email': 'Email',
            'handle': 'Handle',
            'display_name': 'Display name (optional)',
        }
        # THE AUTOCOMPLETE HINTS ARE NOT POLISH. The first real signup on
        # this form arrived with a display name of "proteus375" -- the local
        # part of the signer-up's email address, which a password manager had
        # helpfully offered for a text field it could not identify. Nothing
        # in this code derived it, and nothing had to: the field was blank,
        # public, and next to a login.
        #
        # That is the module docstring's own warning arriving by way of the
        # browser rather than the model. Claiming `username` for the email
        # gives the password manager the field it was looking for, and
        # `nickname` tells it what the display name actually is.
        widgets = {
            'email': forms.EmailInput(attrs={'autocomplete': 'username'}),
            'handle': forms.TextInput(attrs={'autocomplete': 'off'}),
            'display_name': forms.TextInput(attrs={'autocomplete': 'nickname'}),
        }

    def clean_email(self):
        """Lowercased before the uniqueness check, not after.

        Django checks `unique` against the value as typed. Without this,
        Ada@example.com and ada@example.com are two accounts that can both
        sign in and are the same mailbox -- which is Defect 1 from the design
        document arriving by a different route.
        """
        return (self.cleaned_data['email'] or '').strip().lower()

    def clean_handle(self):
        return (self.cleaned_data['handle'] or '').strip().lower()

    def save(self, commit=True):
        account = super().save(commit=False)
        account.terms_accepted_at = timezone.now()
        # Signing up is the act that creates a public identity, so it is
        # stamped in the same breath as the terms rather than left to the
        # model default -- which is False, deliberately. See
        # `Account.is_public`. A ModelForm builds its own instance, so this
        # does not go through `AccountManager.create_user`.
        account.is_public = True
        if commit:
            account.save()
        return account


class ProfileForm(forms.ModelForm):
    """What a person may change about how they appear.

    Not the email and not the handle. The email is a credential and changing
    it is an authentication flow of its own; the handle is an address other
    people may already have linked to, and letting it move silently would
    break those links and free the old one for somebody else to take -- which
    is how an impersonation works.
    """

    class Meta:
        model = Account
        fields = ['display_name']
        labels = {'display_name': 'Display name'}
        help_texts = {
            'display_name': 'Leave this blank to be shown by your handle.',
        }
        # See the note on SignUpForm.Meta.widgets. This form is a smaller
        # target -- one field, and nobody arrives at it from a login -- but
        # it publishes the same value, so it makes the same claim.
        widgets = {
            'display_name': forms.TextInput(attrs={'autocomplete': 'nickname'}),
        }
