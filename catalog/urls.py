"""Catalogue URLs.

`plans/new/` is declared before `plans/<slug>/` because both match the same
path and the first one wins. The slug side is guarded too -- `RESERVED_SLUGS`
in forms.py refuses a title that would slugify to one of these -- because
relying on declaration order alone means the day somebody reorders this list
for tidiness, a plan called "New" starts shadowing the page that creates one.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('plans/', views.plans, name='plans'),
    path('plans/new/', views.new_plan, name='new_plan'),
    path('plans/yours/', views.your_plans, name='your_plans'),
    path('plans/<slug:slug>/', views.listing, name='listing'),
    path('plans/<slug:slug>/edit/', views.edit_plan, name='edit_plan'),
]
