"""Reviews, and the acquisition that has to exist before one can be written.

§5 of the design document defers the review system, so this is a decision
rather than a transcription. It leaves two constraints and this migration is
both of them: "reputation and points attach to the person or organisation
layer, never the installation", and "sockpuppet resistance and entitlement
integrity are the same problem wearing two hats".

`Acquisition` is what makes the second true. A review requires one, so farming
reputation costs what acquiring the material costs -- a subscription, per
household -- instead of an afternoon of throwaway accounts.

IT CANNOT BE ADDED LATER, which is why it lands before anything can be
downloaded. A review written before this model existed would have no
acquisition behind it and no way to establish one afterwards: the download
already happened, unrecorded. The same argument that put `TermsAcceptance`
in 0001.

`pack_sha256` and `version` record WHICH pack was taken. A listing can be
revised, and somebody who acquired version 1 reviewed version 1 -- so the
review says so, and a rewrite does not inherit its praise.

Nothing to backfill. Downloading is owner-only until `billing` exists, and an
author holding their own work is not an acquisition -- `record_acquisition`
refuses to write one, because a row saying otherwise would be the first lie in
the table reputation is computed from.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_listing_pack'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Acquisition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pack_sha256', models.CharField(blank=True, max_length=64)),
                ('version', models.CharField(blank=True, max_length=20)),
                ('acquired_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acquisitions', to=settings.AUTH_USER_MODEL)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acquisitions', to='catalog.listing')),
            ],
            options={
                'ordering': ['-acquired_at'],
                'constraints': [
                    models.UniqueConstraint(fields=('account', 'listing'), name='one_acquisition_per_account_per_listing'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(choices=[(1, 'Would not use again'), (2, 'Some of it worked'), (3, 'Worth using'), (4, 'Would recommend'), (5, 'Would use again with another child')])),
                ('body', models.TextField(blank=True, help_text='What worked, what you would change, who it suited.')),
                ('version_reviewed', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to=settings.AUTH_USER_MODEL)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='catalog.listing')),
            ],
            options={
                'ordering': ['-created_at'],
                'constraints': [
                    models.UniqueConstraint(fields=('account', 'listing'), name='one_review_per_account_per_listing'),
                ],
            },
        ),
    ]
