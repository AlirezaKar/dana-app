"""URLs for app_account — the login page and the session helpers."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.login, name='login'),
    path('login/', views.login, name='login_post'),
    path('logout/', views.logout, name='logout'),
    path('login/check-user/', views.check_user, name='check_user'),
    path('session/ping/', views.session_ping, name='session_ping'),
]
