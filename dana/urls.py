"""Root URL configuration for the DANA case-registration system."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # development helpers: /dev/setting/ (only active when DANA['DEV_TOOLS'])
    path('', include('app_core.urls')),
    path('records/', include('app_records.urls')),
    path('media/', include('app_media.urls')),
    path('', include('app_account.urls')),
    path('', include('app_main.urls')),
]
