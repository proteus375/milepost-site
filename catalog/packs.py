"""Where a file from a stranger stops being bytes.

EVERY CHECK HERE IS SOMEBODY ELSE'S CODE, ON PURPOSE
------------------------------------------------------
The zip bombs, the entry-name allowlist, the content sniffing, the hash
verification and the document parser all live in `courselms_format`, which
`homeschool-lms` uses to build the packs this reads. §D asks this project to
"re-validate independently with its own copy of the parser, trusting nothing",
and one version-pinned package is that: this project decides which version it
runs, and cannot accidentally run a subtly different one.

What this module adds is the part that is genuinely local: a ceiling before
the format is invoked at all, a filename the uploader does not choose, and the
decision about what gets recorded.

THE UPLOADER DOES NOT NAME THE FILE
------------------------------------
`pack_path` ignores the uploaded name entirely and returns random hex. An
uploaded filename is attacker-controlled text that would otherwise become a
path on this server -- and every mitigation for that is a thing to get right,
where not using it at all is nothing to get wrong. The same reasoning the
format itself applies to media entries, which are named by hash and matched
rather than sanitised.

WHAT THE MANIFEST SAYS IS NOT WHAT IS TRUE
-------------------------------------------
A manifest names an owner. That name is written by whoever built the pack, so
it is recorded and never believed: the listing's owner is the one this site
established when somebody signed in, and §D's step 4 -- verifying the named
identity really is linked to the installation that sent it -- needs a machine
channel that does not exist yet. Until `instances` does, the uploader is the
authority, and the manifest's claim is evidence rather than fact.
"""

import hashlib
import secrets

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from courselms_format import CoursePackError, read

#: Refused before the archive is opened. The format's own ceiling is 256MB
#: uncompressed; this is a cheaper refusal that happens first, and it is
#: deliberately well under it -- a course plan of shared reading, images and
#: worksheets is single-digit megabytes, and a pack near this size is a
#: question rather than a course.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024


def pack_path(instance, filename):
    """A name this server chose. See the module docstring."""
    return f'packs/{secrets.token_hex(16)}.coursepack'


def inspect(data):
    """Validate a pack and return what a listing should record about it.

    Raises `ValidationError` with a message fit to show the person who
    uploaded the file -- `CoursePackError`'s messages are already written to
    be shown, so they are passed through rather than replaced with something
    vaguer.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            'That file is larger than a course pack is allowed to be.'
        )

    try:
        manifest, parsed, media = read(data)
    except CoursePackError as error:
        raise ValidationError(str(error)) from error

    pages = sum(len(module['pages']) for module in parsed['modules'])
    return {
        'pack_sha256': hashlib.sha256(data).hexdigest(),
        'pack_bytes': len(data),
        'pack_uploaded_at': timezone.now(),
        'pack_manifest': manifest,
        'pack_course_name': parsed['name'],
        'pack_module_count': len(parsed['modules']),
        'pack_page_count': pages,
        'pack_media_count': len(media),
    }


def attach(listing, data):
    """Put a validated pack on a listing.

    Takes bytes rather than the upload, so the file is read once. The format
    needs the whole archive anyway -- a zip's index is at its end -- and the
    ceiling above is smaller than any machine this runs on.

    Validated before anything is written, so a refused pack leaves the
    listing exactly as it was.
    """
    facts = inspect(data)

    for field, value in facts.items():
        setattr(listing, field, value)
    # The name given here is discarded: `upload_to` generates the real one.
    # Passing a placeholder rather than the uploader's filename keeps it
    # obvious that the uploader never names anything on this disk.
    listing.pack.save('pack.coursepack', ContentFile(data), save=False)
    listing.save()
    return listing
