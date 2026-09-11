"""The machine channel's identity, and the link that makes a licence answerable.

§A settles that the seam worth building is human browser traffic versus machine
instance traffic, and the row that decides its shape is the one saying an
instance in the field cannot be redeployed on your schedule. Everything here is
a thing that has to be right before a single deployment holds a credential.

`Installation.identifier` is a UUID rather than the primary key because it
travels: it is what the machine authenticates as and it appears inside every
licence document. A sequential id would tell any holder how many installations
exist and let them guess the next one.

`Installation.organisation` is §C.4.3's installation layer, and it lands in the
first migration for the same reason §C.4.5 put the listing's owner columns in
one: a publish is only attributable if the machine channel proves which
installation is speaking and the installation names the only organisation it
may publish as. Adding it later means re-deciding attribution for packs already
pushed.

`InstallationLink` is the answer to the only question this app is asked today.
§A: "issuing a licence for a co-op means reading every household attached to
that installation, and that is one join, not a fan-out of service calls." This
table is that join. Nothing else in either database records which deployment a
guardian uses.

There is no registration endpoint and therefore no row here that anybody but an
operator can create. See `instances/models.py`.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0004_account_subject'),
    ]

    operations = [
        migrations.CreateModel(
            name='Installation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.UUIDField(default=uuid.uuid4, editable=False, help_text='The id this installation authenticates as.', unique=True)),
                ('name', models.CharField(help_text='Who this was provisioned for. For operators, not for the machine.', max_length=120)),
                ('signing_key', models.CharField(editable=False, max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('organisation', models.ForeignKey(blank=True, help_text='Set for a co-op installation. This is the only organisation it may publish as.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='installations', to='accounts.organisation')),
            ],
            options={
                'ordering': ['name', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='InstallationLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('linked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installation_links', to='accounts.account')),
                ('installation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='links', to='instances.installation')),
            ],
            options={
                'ordering': ['installation', 'account'],
            },
        ),
        migrations.AddConstraint(
            model_name='installationlink',
            constraint=models.UniqueConstraint(fields=('installation', 'account'), name='one_link_per_account_per_installation'),
        ),
    ]
