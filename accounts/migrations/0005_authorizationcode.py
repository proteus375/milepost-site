"""The five minutes between a guardian consenting and their instance collecting.

§C.1's layer 2. The marketplace is the identity provider and an installation is
the client, and what the client gets at the end is not an access token -- it is
the opaque subject id §C.1 says the instance stores against its local user, plus
the link that makes it usable. `accounts.models.AuthorizationCode` explains why
a bearer token would be a credential with nothing to open.

IN `accounts` RATHER THAN `instances`, ON §A'S INSTRUCTION. That section's app
table gives `accounts` "marketplace identity, OAuth provider endpoints, profile,
organisations", and this is the OAuth provider. The model is installation-shaped
enough that `instances` was tempting, and tidiness is not a good enough reason to
depart from a settled line -- especially one whose whole purpose is to say where
a reader should look.

The dependency therefore runs both ways at the app level and neither way at the
import level: the foreign key is a string reference, and `accounts` imports
nothing from `instances`.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_account_subject'),
        ('instances', '0002_installation_redirect_uri'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthorizationCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(editable=False, max_length=64, unique=True)),
                ('code_challenge', models.CharField(max_length=128)),
                ('redirect_uri', models.URLField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('redeemed_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authorization_codes', to='accounts.account')),
                ('installation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authorization_codes', to='instances.installation')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
