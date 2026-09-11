"""Generate the Ed25519 keypair the licence documents are signed with.

A command rather than a paragraph in a README, because the one thing that must
not happen is somebody generating this with a snippet they found and getting
the encoding subtly wrong -- a key that works here and produces signatures no
instance can verify is a failure nobody sees until it is in the field.

It prints and stores nothing. The operator copies the private half into the
environment and the public half into the `homeschool-lms` release, which is the
only pair of places either belongs.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate an Ed25519 keypair for signing licence documents.'

    def handle(self, *args, **options):
        private = Ed25519PrivateKey.generate()
        private_b64 = base64.b64encode(private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )).decode('ascii')
        public_b64 = base64.b64encode(private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )).decode('ascii')

        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'Private half. Goes in the marketplace environment and nowhere '
            'else. It is not stored by this command.'
        ))
        self.stdout.write(f'LICENCE_SIGNING_KEY={private_b64}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'Public half. Ships inside the homeschool-lms release so an '
            'instance can verify a cached licence with no network.'
        ))
        self.stdout.write(f'LICENCE_PUBLIC_KEY={public_b64}')
        self.stdout.write('')
        self.stdout.write(
            'Rotating this invalidates every cached licence in the field '
            'until instances pick up a release carrying the new public half. '
            'That is a coordinated change, not a routine one.'
        )
