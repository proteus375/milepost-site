"""Which family took a copy, and which family's opinion a review is.

§H.6 of the design document settles the rule: an acquisition, a review and a
threshold badge count once per household, not once per account. §B.3 is why
that is not the same thing -- a household is "one subscription plus one or
more linked marketplace identities", so the fan-out from subscription to
account is set by the subscriber, and counting accounts overstates by exactly
that factor. Two parents on one subscription who both liked a plan have one
household's experience of it.

WHY THE COLUMN RATHER THAN A JOIN. `Acquisition` and `Review` both already
carry the `account`, and an account resolves to a household -- so the counting
could be a join and the constraint could not. A UniqueConstraint does not span
one. Beyond that, resolving it live would be wrong rather than merely slower:
people move between households, a separated couple becomes two, and the
household that took a copy is a fact about the day it happened. A membership
change must not retroactively re-attribute somebody's download.

THIS IS NOT A BACKFILL, WHICH IS WHY IT COULD BE DONE NOW -- BUT IT HAS A
PRECONDITION, AND THE FIRST DRAFT OF THIS DOCSTRING GOT IT WRONG IN A WAY
WORTH RECORDING.

What is true: no path through the application can write an `Acquisition`.
`download_pack` refused every reader who could not already edit the listing,
and `record_acquisition` refuses to record an editor -- "an author holding
their own work is not an acquisition". A `Review` requires an acquisition, so
it follows for that table too. The nullable-then-not-null pair below is two
steps over nothing when that holds.

What does not follow, and what the first draft asserted anyway, is that the
tables are therefore empty EVERYWHERE. A shell is not a path through the
application. This migration failed the first time it ran, on a development
database holding one seeded acquisition and its review -- written two
milliseconds apart by a script somebody used to look at the reviews page. The
reasoning about the application was sound; generalising from "the app cannot
write this" to "this cannot exist" was not.

So the precondition is enforced rather than assumed. `refuse_if_rows_exist`
runs first and stops with a sentence saying what to do, because the
alternative is a sixty-line traceback out of the SQLite table-remake that
reports a NOT NULL violation and nothing about why anybody expected
otherwise.

IT REFUSES RATHER THAN DELETING. A migration that destroys rows to make
itself apply is harmless the day it is written and ugly the first time
somebody restores a backup. Clearing a development database is a decision for
whoever owns it, taken in a shell where it is visible, not a side effect of
running `migrate`.

§H.6 also records why this did not have to be first-migration-shaped, unlike
§C.4.5's owner columns and §C.4.7's acceptances. Those record facts that
cannot be reconstructed afterwards -- an unrecorded download, an acceptance
never captured. Household membership is durable and every row carries the
account that resolves to one, so had rows existed the backfill would have been
a join rather than an archaeology. The reason it may wait is specific and does
not generalise.
"""

from django.db import migrations, models
import django.db.models.deletion


def refuse_if_rows_exist(apps, schema_editor):
    """Stop with an explanation rather than an IntegrityError.

    `household` is not nullable and there is nothing to derive it from: an
    account resolves to a household only once somebody has put it on one, and
    inventing one to satisfy a constraint would be writing down a billing
    arrangement nobody agreed to.
    """
    acquisitions = apps.get_model('catalog', 'Acquisition').objects.count()
    reviews = apps.get_model('catalog', 'Review').objects.count()
    if not acquisitions and not reviews:
        return
    raise RuntimeError(
        'This migration gives every acquisition and review a required '
        'household, and there is no way to work out which household rows '
        f'written before it belong to. Found {acquisitions} acquisition(s) '
        f'and {reviews} review(s).\n\n'
        'Nothing is deployed, so these can only be development data -- no '
        'path through the application could have written them. Clear them '
        'and run this again:\n\n'
        '    from django.db import connection\n'
        '    c = connection.cursor()\n'
        '    c.execute("DELETE FROM catalog_review")\n'
        '    c.execute("DELETE FROM catalog_acquisition")\n\n'
        'If this ever fires on a database that matters, do not delete '
        'anything. Those rows need a household each, and that is a data '
        'migration somebody has to write on purpose.'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
        ('catalog', '0003_reviews'),
    ]

    operations = [
        migrations.RunPython(
            refuse_if_rows_exist, migrations.RunPython.noop, elidable=False,
        ),
        migrations.AddField(
            model_name='acquisition',
            name='household',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='acquisitions', to='billing.household'),
        ),
        migrations.AddField(
            model_name='review',
            name='household',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reviews', to='billing.household'),
        ),
        migrations.AlterField(
            model_name='acquisition',
            name='household',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='acquisitions', to='billing.household'),
        ),
        migrations.AlterField(
            model_name='review',
            name='household',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reviews', to='billing.household'),
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.UniqueConstraint(fields=('household', 'listing'), name='one_review_per_household_per_listing'),
        ),
    ]
