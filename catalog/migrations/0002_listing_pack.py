"""A listing can carry the pack it describes.

Nine columns and no constraint, which is the shape of an addition rather than
a decision -- the decision that could not wait was the owner, and it is
already in 0001.

Six of the nine are facts about an archive that has already been opened and
validated: its hash, its size, when it arrived, what its manifest claimed, and
what the document inside turned out to contain. They are stored rather than
recomputed because reopening a zip to render a listing page would put an
archive parse on the path of every anonymous page view, which is a denial of
service somebody else gets to schedule.

`pack_manifest` is what the pack said about itself. A manifest names an owner,
and that name is written by whoever built the archive -- so it is recorded and
never believed. Verifying that the named identity really is linked to the
installation that sent it is §D's step 4, and it needs a machine channel that
does not exist yet.

Nothing to backfill: no listing has a pack, because until now there was
nowhere to put one.
"""

from django.db import migrations, models

import catalog.packs


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='pack',
            field=models.FileField(blank=True, upload_to=catalog.packs.pack_path),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_sha256',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_bytes',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_uploaded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_manifest',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_course_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_module_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_page_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='listing',
            name='pack_media_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
