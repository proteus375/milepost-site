"""The machine channel's end of the identity bridge.

WHAT AN INSTALLATION IS. One deployment of `homeschool-lms` that the business
runs for a customer -- a family or a co-op. §B.5 settled that the business
hosts every instance, which is why this model exists at all: there is a known
set of deployments, each provisioned deliberately, rather than an open world of
self-hosters.

PROVISIONED, NOT SELF-REGISTERING, AND THAT IS A DECISION
-----------------------------------------------------------
§C.1 says "on first connection the instance registers and receives an
`installation_id` and a secret", which reads like open registration. It is not,
and two other sections settle it: §B.5 concluded that the business hosts every
instance, and §C.4.3 says a co-op installation "is bound to one organisation
**at provisioning**" -- which names an operator doing the binding.

The security argument is the decisive one. An open registration endpoint lets
anybody mint an installation identity, and an installation identity is the
thing every other check on this channel is built on: §D step 4 verifies that a
published pack's named identity is linked to the installation that sent it, and
§C.4.3's publish rule needs the installation bound to the organisation. Both
reduce to "this machine is who it says it is". An endpoint that hands that out
to whoever asks is not a weaker version of the check; it is the absence of one.

So an operator creates the row, the secret is shown once, and it goes into the
deployment's environment. There is no registration endpoint.

THE SIGNING KEY IS STORED, NOT HASHED, AND THAT IS A TRADE RATHER THAN AN
OVERSIGHT
--------------------------------------------------------------------------
The first draft of this model called the column `secret_hash` and stored
`sha256(secret)`, which is what one does with an API token and is incoherent
here. §A specifies a **signed request**, `auth.py` implements that as an HMAC,
and an HMAC can only be verified by a party that holds the signing key. A
one-way hash of it verifies nothing. The two choices do not compose, and
pretending otherwise would have produced a column whose name claimed a property
it did not have.

So the choice is real and it is this:

| | |
| --- | --- |
| **Bearer token, hashed at rest** | A stolen database yields no usable credential. The credential itself travels on every request, so every intermediary that logs an `Authorization` header -- a proxy, a WAF, an error tracker, a request dump pasted into a bug report -- has logged it. |
| **HMAC, key stored** | The credential never travels; a log holds a signature over a method, a path and a timestamp, which is useless anywhere else. A stolen database yields the key. |

**HMAC, and the reasoning is about which failure is likely rather than which is
worse.** Credentials leaking through logs and error reports is mundane, happens
to careful people, and happens repeatedly. A database compromise is rarer and,
if it happens here, has already handed over the packs, the accounts and the
entitlement records -- an installation credential is not the part of that
incident anybody would be worrying about. §A naming a signed request settles
the tie.

What this buys is bounded and worth stating: if this database is read, every
installation credential is read with it, and the response is to rotate all of
them. `rotate_secret` exists for that and takes effect immediately.

The key is write-only in the admin for the same reason a password is: an
operator who has lost one rotates rather than looks it up, so there is no
screen where it can be read over somebody's shoulder or captured in a
screenshot.
"""

import secrets
import uuid

from django.db import models
from django.utils import timezone

#: How long a provisioned secret is, in bytes of entropy before encoding.
SECRET_BYTES = 32


def new_secret():
    """One generator, used by provisioning, rotation and the admin.

    Three call sites had three copies of this line in the first draft, which is
    three chances for one of them to be shortened by somebody who did not know
    why 32 was 32.
    """
    return secrets.token_urlsafe(SECRET_BYTES)


class Installation(models.Model):
    """One deployment of the LMS, and what it is allowed to speak for."""

    #: What goes over the wire. A UUID rather than the primary key, because a
    #: sequential id tells a holder how many installations exist and lets them
    #: guess the next one -- and because this appears in the licence payload,
    #: which is a document that travels.
    identifier = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        help_text='The id this installation authenticates as.',
    )
    #: An operator's label. Never seen by a customer, never authoritative --
    #: `organisation` is what says who this installation may publish as.
    name = models.CharField(
        max_length=120,
        help_text='Who this was provisioned for. For operators, not for the '
                  'machine.',
    )
    #: The shared secret this installation signs with. Stored, because an
    #: HMAC cannot be verified from a hash -- see the module docstring, which
    #: records what that costs and why it was chosen anyway. Write-only in the
    #: admin; a lost secret is rotated, not looked up.
    signing_key = models.CharField(max_length=64, editable=False)

    # §C.4.3's installation layer. Null for a family installation; set at
    # provisioning for a co-op. PROTECT because an organisation is deactivated
    # rather than deleted, and an installation bound to a deleted organisation
    # would be one that may publish as nobody.
    organisation = models.ForeignKey(
        'accounts.Organisation', on_delete=models.PROTECT,
        null=True, blank=True, related_name='installations',
        help_text='Set for a co-op installation. This is the only '
                  'organisation it may publish as.',
    )

    # WHERE THIS DEPLOYMENT LIVES, AND IT IS AN ALLOWLIST OF EXACTLY ONE.
    #
    # §C.1's OAuth flow sends a guardian back to their own instance carrying an
    # authorization code. An authorization server that accepts whatever
    # redirect a request asks for is an open redirect with a credential
    # attached -- the classic way authorization codes are stolen. So the URI is
    # recorded here at provisioning, by the operator who knows where the
    # deployment actually is, and a request naming anything else is refused.
    #
    # Blank means this installation cannot do the OAuth flow at all, which is
    # the right default: an installation provisioned before this field existed
    # has no known address, and guessing one would be inventing the allowlist
    # this field exists to be.
    redirect_uri = models.URLField(
        blank=True,
        help_text=(
            'Where this deployment receives the OAuth redirect, exactly. '
            'Blank means it cannot link accounts.'
        ),
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    #: Written on every authenticated request. The cheapest possible answer to
    #: "is this deployment still talking to us", which is the first question
    #: anybody asks when a customer reports that nothing syncs.
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name or str(self.identifier)

    @classmethod
    def provision(cls, name, organisation=None):
        """Create one and return it with its secret, which is shown once.

        Returned here and not shown again. It is in the database -- it has to
        be, per the module docstring -- but nothing displays it, so the
        operator's copy at provisioning time is the one that matters.
        """
        secret = new_secret()
        installation = cls.objects.create(
            name=name,
            organisation=organisation,
            signing_key=secret,
        )
        return installation, secret

    def rotate_secret(self):
        """A new secret, effective immediately. The old one stops working.

        Immediate rather than overlapping, which is the wrong default for most
        credential rotation and the right one here: the reason to rotate is
        that the old secret may be in somebody else's hands, and a grace window
        is a window in which it still works.
        """
        secret = new_secret()
        self.signing_key = secret
        self.save(update_fields=['signing_key'])
        return secret

    def seen(self):
        self.last_seen_at = timezone.now()
        self.save(update_fields=['last_seen_at'])

    def linked_accounts(self):
        return [link.account for link in self.links.select_related('account')]


class InstallationLink(models.Model):
    """A guardian on this installation, and the marketplace identity they are.

    §C.1's layer 2, recorded on the marketplace side. The instance stores the
    other half -- a local `User` against the `subject` -- and neither side
    stores the other's credential.

    WHY THIS IS NOT DERIVED. "Which households attach to this installation" is
    the query §A says licence issuance comes down to, and there is no other way
    to answer it: a marketplace account has no idea which deployment its owner
    uses, and a deployment has no idea what a household is. This row is the
    only place those two facts meet.

    WHO WRITES IT. Eventually the OAuth flow of §C.1, when a guardian completes
    the link from inside their instance. That flow is not built, so for now an
    operator creates these in the admin alongside the installation -- the same
    provisioning path, and the same reason: there is no self-serve door onto
    this channel yet.

    ONE ACCOUNT MAY BE LINKED TO SEVERAL INSTALLATIONS. A guardian can belong
    to a co-op and run their own instance, and both deployments legitimately
    need to know they are entitled. This opens nothing: entitlement is the
    household's, the household holds one subscription, and appearing in two
    licence payloads does not make it two.
    """

    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='links',
    )
    account = models.ForeignKey(
        'accounts.Account', on_delete=models.CASCADE,
        related_name='installation_links',
    )
    linked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['installation', 'account']
        constraints = [
            models.UniqueConstraint(
                fields=['installation', 'account'],
                name='one_link_per_account_per_installation',
            ),
        ]

    def __str__(self):
        return f'{self.account.handle} on {self.installation}'
