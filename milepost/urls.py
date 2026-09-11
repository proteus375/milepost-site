"""URLs for the public site.

Marketing pages are served straight from `TemplateView` rather than through
an app of their own. §A says "marketing pages start as templates in the same
project", and a `views.py` whose every function renders one template with no
context is a layer that only exists to be read past. When a page needs data
-- pricing from `billing`, listings from `catalog` -- it moves to the app
that owns that data, which is the point at which the indirection earns its
place.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='pages/home.html'),
         name='home'),
    path('themes/', TemplateView.as_view(template_name='pages/themes.html'),
         name='themes'),
    # No prefix. `accounts` owns `signup/`, `login/`, `me/` and `people/<h>/`,
    # which are addresses a person reads and types, not an implementation
    # detail of which app happens to serve them. The handles those paths would
    # otherwise collide with are reserved -- see models.RESERVED_HANDLES.
    path('', include('accounts.urls')),
    # `catalog` owns `plans/`. Same reasoning as above: a person reads and
    # types /plans/a-year-of-botany/, and which app serves it is not their
    # business.
    path('', include('catalog.urls')),
    # THE SEAM. §A: the machine channel gets "its own URL prefix, its own auth,
    # no shared session middleware" -- and the version is in the path from the
    # first URL because "you do not control when a customer upgrades". An
    # instance provisioned today will still be asking for /machine/v1/ long
    # after v2 exists, and that has to keep working or a customer's records
    # stop syncing because of a release they never asked for.
    #
    # `machine/` rather than `api/`, because `api/` invites every other kind of
    # programmatic access to land here -- a mobile app, a webhook, somebody's
    # integration -- and none of those are this. This prefix means one thing:
    # an installation of the LMS, authenticated by a credential an operator
    # provisioned.
    path('machine/v1/', include('instances.urls')),
    path('admin/', admin.site.urls),
]
