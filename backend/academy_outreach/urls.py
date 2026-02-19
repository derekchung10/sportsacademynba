"""
Root URL configuration for Academy Outreach Platform.

In development: React dev server runs on port 5173, Django API on port 8000.
In production: Django serves the React build from frontend/dist/.
"""
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path('api/', include('app.urls')),
    path('health', health_check),
    # Serve React index.html for the root and any non-API routes (client-side routing)
    re_path(r'^(?!api/|health|static/).*$', TemplateView.as_view(template_name='index.html')),
]
