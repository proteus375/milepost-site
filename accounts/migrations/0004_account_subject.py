"""An opaque id an installation can store, because the email address cannot be.

§C.1 of the design document makes this the load-bearing field of the identity
bridge: "the join key is an opaque subject id stored on the local user, never
an email address ... this is not a refinement, it is the thing that makes the
bridge sound at all." `homeschool-lms` has a non-unique `User.email` -- Defect
1 -- so entitlement matched on email would be matched on a field that does not
identify a person.

THREE OPERATIONS, NOT ONE, AND THE MIDDLE ONE IS THE POINT. A UUID default is
a callable, and `AddField` calls it ONCE and writes the same value to every
existing row -- which is then rejected by the unique index, or worse, accepted
and leaves every account sharing one subject. So the column arrives nullable,
a data migration gives each row its own value, and only then does it become
unique and not-null.

This database has accounts in it. That is the difference between this
migration and `catalog/0004`, which could assume empty tables and now refuses
rather than assuming -- the lesson from that one is applied here by writing
the backfill rather than by reasoning about whether it is needed.
"""

import uuid

from django.db import migrations, models


def give_each_account_a_subject(apps, schema_editor):
    Account = apps.get_model('accounts', 'Account')
    for account in Account.objects.filter(subject__isnull=True).iterator():
        # Saved one at a time on purpose. A bulk_update would be faster and
        # this runs once against a table of tens, so the readable version
        # wins.
        account.subject = uuid.uuid4()
        account.save(update_fields=['subject'])


def unset_every_subject(apps, schema_editor):
    """Reverse. The values are not recoverable and should not pretend to be.

    Going backwards past this migration means every instance that stored a
    subject id has been unlinked, which is a thing to know rather than a thing
    to paper over.
    """
    apps.get_model('accounts', 'Account').objects.update(subject=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_organisation'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='subject',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(give_each_account_a_subject, unset_every_subject),
        migrations.AlterField(
            model_name='account',
            name='subject',
            field=models.UUIDField(default=uuid.uuid4, editable=False, help_text='Opaque, stable id an installation stores to identify this person. Never an email address.', unique=True),
        ),
    ]
