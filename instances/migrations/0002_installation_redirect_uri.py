"""Where a guardian comes back to after linking their account.

§C.1's OAuth flow sends somebody to the marketplace to authenticate and sends
them back to their own instance carrying an authorization code. The code is a
bearer credential for the length of its short life, so where it is sent is the
whole question -- an authorization server that honours whatever redirect a
request names is an open redirect with a credential attached, and that is the
classic way authorization codes are stolen.

So this is an allowlist of exactly one, recorded by the operator who knows
where the deployment actually is. It is not something a request can influence.

BLANK IS THE DEFAULT AND THE RIGHT ONE. Every installation provisioned before
this migration has no known address, and the alternative to blank is guessing
one -- inventing the allowlist this field exists to be. A blank value means the
flow refuses, which is a thing an operator can see and fix, rather than a redirect
somewhere nobody chose.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('instances', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='installation',
            name='redirect_uri',
            field=models.URLField(blank=True, help_text='Where this deployment receives the OAuth redirect, exactly. Blank means it cannot link accounts.'),
        ),
    ]
