"""URLs for app_media.

``storage/…`` is the read-only **storage browser** (v1.7) opened by the
«مشاهدهٔ پوشهٔ ذخیره‌سازی» button:
``/media/storage/`` → ``storage/files``, ``/media/storage/folder/<path>/`` → folder
detail, ``/media/storage/raw/<path>`` → one file.
"""
from django.urls import path, re_path

from . import storage_views, views

urlpatterns = [
    path('upload/', views.upload, name='media_upload'),
    path('remove/<int:image_id>/', views.remove, name='media_remove'),
    path('confirm-group/', views.confirm_group, name='media_confirm_group'),
    path('serve/<int:image_id>/', views.serve, name='media_serve'),

    # ---- storage browser (read-only) ----
    path('storage/', storage_views.storage_index, name='storage_index'),
    re_path(r'^storage/folder/(?P<subpath>.*?)/?$', storage_views.storage_folder,
            name='storage_folder'),
    re_path(r'^storage/raw/(?P<subpath>.+?)/?$', storage_views.storage_raw,
            name='storage_raw'),
]
