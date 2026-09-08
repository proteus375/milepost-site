"""An owner for a listing that outlives the person who pressed Publish.

There is nothing to own yet, and that is the reason this is here rather than
in the commit that brings `catalog`. §C.4.5 of the design document: "the
listing's owner shape is in the first migration". Adding an alternative owner
type afterwards means migrating every published listing and re-deciding
attribution for content people are already linking to -- while they are
linking to it.

The failure it prevents is specific. A listing owned only by the individual
who published it carries a departed organiser's name, cannot be maintained by
the co-op that collectively wrote it, and has no owner at all the day that
person deletes their account. An organisation is the owner; the membership row
is what changes when people come and go.

MINIMAL BY §C.4.6, WITH ONE DEPARTURE. That section separates what must be
settled now -- id, slug, name, is_active -- from what can follow, and puts the
membership ROLES in the second column. They are here anyway, because §C.4.7's
`TermsAcceptance` is the next model in this sequence and it draws a line that
needs them: a PUBLISHER may not accept terms on the organisation's behalf,
because accepting them is an ownership act. A column added in the very next
commit is the same column with a migration in between.

Nothing here is a data migration. Nothing has been published, so there is
nothing to attribute.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

import accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_account_is_public'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organisation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='The address this organisation is linked at. It must survive every membership change, so it is not something a member edits.', max_length=30, unique=True, validators=[accounts.models.validate_handle])),
                ('name', models.CharField(help_text='What people see. A co-op\u2019s name, not an abbreviation.', max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'ordering': ['slug'],
            },
        ),
        migrations.CreateModel(
            name='OrganisationMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('OWNER', 'Owner'), ('PUBLISHER', 'Publisher')], default='PUBLISHER', max_length=12)),
                ('added_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='organisation_memberships', to='accounts.account')),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='memberships_granted', to='accounts.account')),
                ('organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='accounts.organisation')),
            ],
            options={
                'ordering': ['organisation', 'account'],
            },
        ),
        migrations.AddField(
            model_name='organisation',
            name='members',
            field=models.ManyToManyField(related_name='organisations', through='accounts.OrganisationMembership', through_fields=('organisation', 'account'), to='accounts.account'),
        ),
        migrations.AddConstraint(
            model_name='organisationmembership',
            constraint=models.UniqueConstraint(fields=('organisation', 'account'), name='one_membership_per_account_per_organisation'),
        ),
    ]
