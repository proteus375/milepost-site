"""The periodic pass, as something a person can run and read.

§H.9 asks for "a periodic pass for `SUSTAINED`, which is the only one that
turns true with no event behind it". This is it, and it applies the other rule
too -- `awarding.run` says why `PUBLISHED` needs a pass despite having an
event of its own.

SAFE TO RUN TWICE, AND THE HELP TEXT SAYS SO. Every rule is idempotent and
none of them revoke, so an operator who thinks something has gone wrong can
run this without first having to reason about what it will do to rows that are
already right.

IT PRINTS WHAT IT GRANTED, NOT HOW MANY. A badge is a public statement about
somebody, and "granted 14" gives whoever ran it no way to notice that one of
the fourteen is wrong.
"""

from django.core.management.base import BaseCommand

from catalog import awarding


class Command(BaseCommand):
    help = (
        'Grant the badges whose rules have become true. Idempotent: a second '
        'run grants nothing the first did not, and nothing here ever revokes.'
    )

    def handle(self, *args, **options):
        result = awarding.run()
        new = result['new']

        if not new:
            self.stdout.write(
                f'Nothing new. {len(result["granted"])} badge(s) already '
                f'granted and still earned.'
            )
            return

        for award in new:
            self.stdout.write(self.style.SUCCESS(
                f'{award.get_kind_display()} to {award.subject}: {award.reason}'
            ))
