"""Writing a plan down. Not publishing it -- see the note in views.py."""

from django import forms
from django.utils.text import slugify

from accounts.models import Organisation

from . import packs
from .models import GRADE_MAX, GRADE_MIN, Listing, grade_label

GRADE_CHOICES = [(n, grade_label(n)) for n in range(GRADE_MIN, GRADE_MAX + 1)]

#: Addresses `catalog.urls` claims for itself. A plan called "New" would
#: otherwise take a slug that shadows the page for creating one -- the same
#: class of collision RESERVED_HANDLES exists for, at a different level of
#: the path.
RESERVED_SLUGS = frozenset({'new', 'yours', 'edit', 'publish'})


class PlanForm(forms.ModelForm):
    """The plan itself, plus who it belongs to.

    THE OWNER IS CHOSEN ONCE AND NOT AGAIN. It is on the create form and
    absent from the edit form, because moving a listing between an individual
    and a co-op is a transfer of ownership -- the thing §C.4 is entirely
    about -- and not an edit to a field. When that needs to be possible it
    needs a deliberate flow, an audit trail, and probably both owners'
    agreement; a dropdown that quietly reassigns it is none of those.
    """

    owner = forms.ChoiceField(
        label='Published by',
        help_text=(
            'A co-op keeps its plans when the person who wrote them moves on. '
            'This cannot be changed afterwards.'
        ),
    )

    class Meta:
        model = Listing
        fields = ['title', 'summary', 'description', 'subject',
                  'grade_min', 'grade_max']
        labels = {
            'summary': 'Summary',
            'description': 'What it covers',
            'grade_min': 'From grade',
            'grade_max': 'To grade',
        }
        widgets = {
            'grade_min': forms.Select(choices=GRADE_CHOICES),
            'grade_max': forms.Select(choices=GRADE_CHOICES),
            'description': forms.Textarea(attrs={'rows': 8}),
        }

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        if self.instance.pk:
            del self.fields['owner']
            return
        self.fields['owner'].choices = self.owner_choices()

    def owner_choices(self):
        choices = [('me', f'{self.account.public_name} (you)')]
        for organisation in Organisation.objects.filter(
            memberships__account=self.account, is_active=True,
        ).distinct():
            choices.append((organisation.slug, organisation.name))
        return choices

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get('grade_min'), cleaned.get('grade_max')
        if low is not None and high is not None and low > high:
            # Checked here as well as in the database. The constraint is what
            # makes it true; this is what makes it a sentence rather than an
            # IntegrityError page.
            self.add_error('grade_max', 'The last grade comes after the first.')
        return cleaned

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not self.instance.pk and self.slug_for(title) in RESERVED_SLUGS:
            raise forms.ValidationError('That title is reserved. Try another.')
        return title

    def slug_for(self, title):
        return slugify(title)[:80].strip('-')

    def unique_slug(self, title):
        """Suffixes a taken slug rather than refusing.

        `portability.unique_code` in the LMS does the same thing for course
        codes and for the same reason: two people may reasonably name a plan
        "A Year of Botany", and telling the second one their title is taken
        is a worse answer than giving them botany-2.
        """
        base = self.slug_for(title) or 'plan'
        slug, suffix = base, 1
        while Listing.objects.filter(slug=slug).exists():
            suffix += 1
            tail = f'-{suffix}'
            slug = f'{base[:80 - len(tail)]}{tail}'
        return slug

    def save(self, commit=True):
        listing = super().save(commit=False)
        if not listing.pk:
            listing.slug = self.unique_slug(self.cleaned_data['title'])
            owner = self.cleaned_data['owner']
            if owner == 'me':
                listing.owner_account = self.account
            else:
                listing.owner_organisation = Organisation.objects.get(slug=owner)
        if commit:
            listing.save()
        return listing


class PackForm(forms.Form):
    """The pack, checked before the page comes back.

    Validating in the form rather than the view is what puts a refusal beside
    the field instead of on an error page -- and the format's messages are
    already written to be shown to whoever uploaded the file, so they are
    passed through rather than replaced with something vaguer.

    The bytes are kept on the form after `clean`, so the file is read once.
    An upload is a stream; reading it twice gets nothing the second time.
    """

    pack = forms.FileField(
        label='Course pack',
        help_text=(
            'The .coursepack file Milepost exports from a course. It is '
            'checked here before anything is stored.'
        ),
    )

    def clean_pack(self):
        upload = self.cleaned_data['pack']
        self.data_bytes = upload.read()
        # Raises ValidationError, which the form renders against this field.
        packs.inspect(self.data_bytes)
        return upload

    def attach_to(self, listing):
        return packs.attach(listing, self.data_bytes)
