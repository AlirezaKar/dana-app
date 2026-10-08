"""URLs for app_main (wizard steps)."""
from django.urls import path

from . import views

urlpatterns = [
    path('step2-upload/', views.upload_page, name='step2_upload'),
    path('step3-done/', views.done_page, name='step3_done'),
    path('case/resolve/', views.resolve_case, name='case_resolve'),
    path('victim/add/', views.add_victim, name='victim_add'),
    path('victim/remove/', views.remove_victim, name='victim_remove'),
    path('finish/', views.finish, name='finish'),
    path('restart/', views.restart, name='restart'),
]
