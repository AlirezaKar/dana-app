"""URLs of the shared app (development helpers)."""
from django.urls import path

from . import views

urlpatterns = [
    path('dev/setting/', views.dev_setting, name='dev_setting'),
    path('wm-info/', views.wm_info, name='wm_info'),
]
