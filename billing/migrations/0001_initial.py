"""The entitlement unit, which is the household and could not be anything else.

§B.3 settles the reasoning and §3's Defect 2 forces it: the LMS cannot compute
a family. There is no household model there and no adult-to-adult link, and
inferring one from shared children breaks on exactly the cases that model's
own docstring calls ordinary -- separated parents, an involved grandparent. So
the household is a marketplace-side concept, and the humans decide who is on
it.

WHY THIS LANDS BEFORE STRIPE. Nothing here talks to a payment processor.
`entitled_through` is a date an operator sets, and Stripe's job when it
arrives is to set that same date from a webhook. Splitting them this way means
the half that gates downloads -- the half everything else is waiting on -- can
be built and tested with no external dependency, no test-mode account and no
webhook tunnel, and the half that cannot be tested from anywhere but a real
Stripe account is a smaller change against a schema that already works.

WHAT IS DELIBERATELY NOT HERE. §B.3's signed token: Ed25519, a daily refresh,
a grace window, and two staleness rules that must not be confused. All of it
exists so an installation in the field can verify entitlement offline, and
there is no `instances` app, so nothing would read it. A signed message with
no reader is not a foundation, it is a key to manage. It arrives with the app
that consumes it and reads these same rows.

`one_household_per_account` is unique on `account` alone rather than on the
pair, and that is the load-bearing line in this file. The pair version reads
naturally and permits one person on six households, which is six
subscriptions' worth of entitlement for the price of one -- the door §5 names
when it says sockpuppet resistance and entitlement integrity are the same
problem.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0003_organisation'),
    ]

    operations = [
        migrations.CreateModel(
            name='Household',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='What the people on it call it. Only they ever see it.', max_length=120)),
                ('entitled_through', models.DateField(blank=True, help_text='Paid up to and including this date. Blank means never entitled. Set by hand until Stripe sets it.', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'ordering': ['name', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='HouseholdMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('OWNER', 'Owner'), ('MEMBER', 'Member')], default='MEMBER', max_length=12)),
                ('added_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='household_memberships', to='accounts.account')),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='household_memberships_granted', to='accounts.account')),
                ('household', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='billing.household')),
            ],
            options={
                'ordering': ['household', 'account'],
            },
        ),
        migrations.AddField(
            model_name='household',
            name='members',
            field=models.ManyToManyField(related_name='households', through='billing.HouseholdMembership', through_fields=('household', 'account'), to='accounts.account'),
        ),
        migrations.AddConstraint(
            model_name='householdmembership',
            constraint=models.UniqueConstraint(fields=('account',), name='one_household_per_account'),
        ),
    ]
