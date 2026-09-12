"""Account URLs.

`people/<handle>/` rather than `users/<id>/`: the address is a public identity
and should read as one, and an id in a URL is a count of how many accounts
exist that nobody needs to publish.

The handle is the address, which is why `ProfileForm` will not let anybody
change theirs -- see the note there.
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import oauth, views

urlpatterns = [
    path('signup/', views.sign_up, name='sign_up'),
    # §C.1's consent screen. The human half of the linking flow: a person, a
    # session and a page. Its partner -- the token exchange -- is a
    # server-to-server POST and lives on the versioned machine prefix, because
    # that half is an address an installation in the field constructs. See
    # `accounts/oauth.py` for why the flow is split across two URL spaces
    # rather than forced into one.
    path('oauth/authorize/', oauth.authorize, name='oauth_authorize'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/log_in.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    # POST only, which is Django's default since 4.1 and is the reason to use
    # its view rather than write one: a GET that logs somebody out can be
    # triggered by an image tag on any page they visit.
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('me/', views.edit_profile, name='edit_profile'),
    path('people/<str:handle>/', views.profile, name='profile'),
]
