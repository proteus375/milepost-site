"""The catalogue, and the terms that make a publication answerable.

Two models, and the reason both are here in the first migration rather than
one now and one later is §C.4.5 and §C.4.7 saying the same thing about
different rows.

`Listing` carries three owner references and a constraint that exactly one
owner is set. Adding an alternative owner type afterwards means migrating
every published listing and re-deciding attribution for content people are
already linking to.

`TermsAcceptance` has to exist before the first publish, not after it.
Acceptance can only be recorded going forward, so a model added later leaves
every listing published before it with no provable acceptance behind it --
which is precisely the evidence §4.4.4 says the warranty exists to produce.

The two share a shape on purpose: two nullable subject references, exactly one
set, plus a not-null record of the person who acted. "Who is answerable for
this listing" and "who accepted the terms that make them answerable" have to
have the same possible answers, or there will be listings whose owner never
agreed to anything.

No pack yet. `courselms.coursepack/1` arrives once both repositories read the
format through one shared package rather than two copies that drift.
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
            name='Listing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('slug', models.SlugField(help_text='The address this plan is linked at. It does not change.', max_length=80, unique=True)),
                ('summary', models.CharField(help_text='One or two sentences, shown in the list of plans.', max_length=300)),
                ('description', models.TextField(blank=True, help_text='What the plan covers, who it suits, what it assumes.')),
                ('subject', models.CharField(choices=[('LANGUAGE_ARTS', 'Language arts'), ('MATHEMATICS', 'Mathematics'), ('SCIENCE', 'Science'), ('HISTORY', 'History and social studies'), ('LANGUAGES', 'World languages'), ('ARTS', 'Art and music'), ('HEALTH', 'Health and physical education'), ('COMPUTING', 'Computing'), ('RELIGION', 'Religious studies'), ('LIFE_SKILLS', 'Life skills'), ('OTHER', 'Other')], max_length=20)),
                ('grade_min', models.PositiveSmallIntegerField(default=0)),
                ('grade_max', models.PositiveSmallIntegerField(default=12)),
                ('version', models.CharField(default='1', max_length=20)),
                ('licence', models.CharField(default='milepost-1.0', max_length=40)),
                ('terms_version', models.CharField(blank=True, help_text='The publisher terms in force when this was published. Blank until it is.', max_length=20)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('IN_REVIEW', 'In review'), ('PUBLISHED', 'Published'), ('WITHDRAWN', 'Withdrawn')], default='DRAFT', max_length=12)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('contributed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contributions', to='accounts.account')),
                ('owner_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='listings', to='accounts.account')),
                ('owner_organisation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='listings', to='accounts.organisation')),
            ],
            options={
                'ordering': ['-published_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TermsAcceptance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('terms_version', models.CharField(max_length=20)),
                ('accepted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='terms_acceptances', to='accounts.account')),
                ('accepted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='terms_accepted_for_others', to='accounts.account')),
                ('organisation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='terms_acceptances', to='accounts.organisation')),
            ],
            options={
                'ordering': ['-accepted_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='listing',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('owner_account__isnull', False), ('owner_organisation__isnull', True)), models.Q(('owner_account__isnull', True), ('owner_organisation__isnull', False)), _connector='OR'), name='listing_has_exactly_one_owner'),
        ),
        migrations.AddConstraint(
            model_name='listing',
            constraint=models.CheckConstraint(condition=models.Q(('grade_min__lte', models.F('grade_max'))), name='listing_grade_range_is_a_range'),
        ),
        migrations.AddConstraint(
            model_name='termsacceptance',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('account__isnull', False), ('organisation__isnull', True)), models.Q(('account__isnull', True), ('organisation__isnull', False)), _connector='OR'), name='terms_acceptance_has_exactly_one_subject'),
        ),
        migrations.AddConstraint(
            model_name='termsacceptance',
            constraint=models.UniqueConstraint(condition=models.Q(('account__isnull', False)), fields=('account', 'terms_version'), name='one_acceptance_per_account_per_version'),
        ),
        migrations.AddConstraint(
            model_name='termsacceptance',
            constraint=models.UniqueConstraint(condition=models.Q(('organisation__isnull', False)), fields=('organisation', 'terms_version'), name='one_acceptance_per_organisation_per_version'),
        ),
    ]
