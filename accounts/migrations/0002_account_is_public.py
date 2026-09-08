"""A login and a public presence become two different things.

`Account` is both the marketplace identity and the Django auth user, so until
this field existed an operator running `createsuperuser` was handed a page at
/people/<their handle>/ announcing them as a Milepost member. They had asked
for a login. Nobody involved intended to publish them.

The default is False and every ordinary door sets it True -- see the note on
the field itself. That direction is the point: an account arriving by a route
nobody has thought of yet is private, so the failure is a member wondering
where their page went rather than somebody appearing on the site who never
asked to.

WHICH MAKES THIS A MIGRATION THAT HAS TO BACKFILL. Every account already in
the database predates the field and would take that False, so the people who
did sign up would silently lose the page they signed up for. `Backfill` marks
them public by the record of the act that made them members -- a signup is
the only thing that stamps `terms_accepted_at`, and it is the same condition
`SignUpForm.save()` now writes both halves of. Staff are excluded even if
somebody stamped them, because that is the case this whole migration exists
to close.
"""

from django.db import migrations, models


def publish_the_people_who_signed_up(apps, schema_editor):
    Account = apps.get_model('accounts', 'Account')
    Account.objects.filter(
        terms_accepted_at__isnull=False, is_staff=False,
    ).update(is_public=True)


def unpublish_everybody(apps, schema_editor):
    """Reversing puts the column back to its default, not to guesswork.

    There is nothing to restore to: before this migration nobody had the
    field, so the honest reverse is the state the field was added in.
    """
    Account = apps.get_model('accounts', 'Account')
    Account.objects.update(is_public=False)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='is_public',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Whether this person has a page at /people/<handle>/. Set '
                    'when somebody signs up; staff accounts are logins, not '
                    'members.'
                ),
            ),
        ),
        migrations.RunPython(
            publish_the_people_who_signed_up, unpublish_everybody,
        ),
    ]
