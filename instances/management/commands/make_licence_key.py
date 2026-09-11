"""Generate the Ed25519 keypair the licence documents are signed with.

A command rather than a paragraph in a README, because the one thing that must
not happen is somebody generating this with a snippet they found and getting
the encoding subtly wrong -- a key that works here and produces signatures no
instance can verify is a failure nobody sees until it is in the field.

THE PRIVATE HALF IS NEVER PRINTED, AND THAT IS THE SECOND LESSON
------------------------------------------------------------------
The first version wrote both halves to stdout with a stern warning above the
private one. It was used twice and the private key was pasted into a chat
transcript both times -- not through carelessness, but because the entire
workflow around this project is "run the command, paste what it printed", and
a warning does not change what a terminal buffer is.

So the ergonomics were the defect, not the discipline. The private half now
goes straight into the env file and is never rendered anywhere a human might
copy it. What is printed is the public half, which is meant to be copied, and
the name of the file that changed.

The general form of this, worth keeping: **if a safe path and a convenient
path differ, the convenient one is the one that will be taken.** Making the
safe path the only path is cheaper than asking for care every time.
"""

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

KEY_NAME = 'LICENCE_SIGNING_KEY'


def read_existing(path, name):
    """The current value of `name` in an env file, or None.

    Blank counts as absent, matching `settings.env` -- `.env.example` ships
    this key with no value, so a fresh copy of it must not read as "already
    configured" and refuse to be filled in.
    """
    if not path.exists():
        return None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith(f'{name}='):
            value = line.split('=', 1)[1].strip()
            return value or None
    return None


def write_key(path, name, value):
    """Set `name` in the env file, replacing the line if it is already there.

    Rewrites in place rather than appending, so running this twice does not
    leave two lines where the second silently wins -- which is the kind of
    file a person reads once, sees the wrong key on the line they looked at,
    and spends an afternoon on.
    """
    line = f'{name}={value}'
    if not path.exists():
        path.write_text(line + '\n', encoding='utf-8')
        return

    lines = path.read_text(encoding='utf-8').splitlines()
    for index, existing in enumerate(lines):
        if existing.startswith(f'{name}='):
            lines[index] = line
            break
    else:
        lines.append(line)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


class Command(BaseCommand):
    help = (
        'Generate an Ed25519 keypair for signing licence documents. The '
        'private half is written to the env file; only the public half is '
        'printed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--env-file', default=None,
            help='Where to write the private half. Defaults to .env beside '
                 'manage.py.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Replace a key that is already set. Every licence signed '
                 'with the old one stops verifying.',
        )

    def handle(self, *args, **options):
        path = Path(options['env_file'] or (settings.BASE_DIR / '.env'))

        if read_existing(path, KEY_NAME) and not options['force']:
            raise CommandError(
                f'{KEY_NAME} is already set in {path}. Replacing it '
                'invalidates every licence signed with it, and every '
                'instance in the field keeps rejecting the new ones until it '
                'picks up a release carrying the new public half. If that is '
                'genuinely what you want, pass --force.'
            )

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

        write_key(path, KEY_NAME, private_b64)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Private half written to {path}. It was not printed, and there '
            'is no command that will print it.'
        ))
        self.stdout.write('')
        self.stdout.write(
            'Public half. Safe to copy: it ships inside the homeschool-lms '
            'release so an instance can verify a cached licence with no '
            'network. Keep it somewhere durable -- losing it means re-keying '
            'every installation.'
        )
        self.stdout.write(f'LICENCE_PUBLIC_KEY={public_b64}')
        self.stdout.write('')
        self.stdout.write(
            'Restart any running server; settings read the env file at '
            'startup.'
        )
