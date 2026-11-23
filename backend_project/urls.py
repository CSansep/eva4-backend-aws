"""
URL Configuration for backend_project.

Exposes:
- Core API v1 routes under /api/v1/
- Django Admin interface under /admin/
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Administrative interface
    path('admin/', admin.site.urls),

    # Main API version 1 endpoints
    path('api/v1/', include('core.urls')),
]
