"""The machine channel's URLs, under a version that is in the path on purpose.

§A: the machine channel "needs an explicit version in its path and a real
deprecation policy from day one, because you do not control when a customer
upgrades." The prefix is applied in `milepost/urls.py` rather than here, so
that this module stays the list of what v1 contains and the mounting decision
stays with the other mounting decisions.

`name=` is prefixed `machine_` throughout. The human channel and this one will
eventually both have a route about the same noun -- a pack, a listing -- and
`reverse('pack')` resolving to whichever was registered last is a bug that
takes a long afternoon to see.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('licence/', views.licence, name='machine_licence'),
    # GET lists, POST pushes. See `views.plans`.
    path('plans/', views.plans, name='machine_plans'),
    path('plans/<slug:slug>/', views.plan, name='machine_plan'),
    path('plans/<slug:slug>/pack/', views.pack, name='machine_pack'),
]
