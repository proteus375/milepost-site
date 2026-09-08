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
    path('admin/', admin.site.urls),
]
