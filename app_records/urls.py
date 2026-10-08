"""URLs for app_records (AJAX search endpoint)."""
from django.urls import path

from . import views

urlpatterns = [
    path('search/', views.search, name='records_search'),
    path('details/', views.details, name='records_details'),
]
