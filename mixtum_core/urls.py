"""
URL configuration for mixtum_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path
from django.views.static import serve

from mixtum_core import health


def public_branding_media(request, path):
    """Serve only public branding files from the local instance volume."""
    if not settings.SERVE_LOCAL_BRANDING_MEDIA or getattr(settings, "USE_S3", False):
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT / "branding")

urlpatterns = [
    path('health/live/', health.live, name='health-live'),
    path('health/ready/', health.ready, name='health-ready'),
    path('api/workspace/', include('base_modules.workspace.urls')),
    path('api/branding/', include('base_modules.branding.urls')),
    path('media/branding/<path:path>', public_branding_media, name='public-branding-media'),
]

for plugin in settings.MIXTUM_PLUGINS:
    urlpatterns.append(path(plugin.url_prefix, include((plugin.urlconf, plugin.id), namespace=plugin.id)))

if getattr(settings, 'AUTH_MODE', 'django') == 'django':
    from base_modules.celery.views import flower_auth

    # Legacy endpoints stay available only while the current Django auth mode is active.
    # Each must be scoped and reviewed before being exposed with Keycloak Bearer tokens.
    urlpatterns += [
        path('admin/', admin.site.urls),
        path('flower-auth/', flower_auth, name='flower-auth'),
        path('api/v1/accounts/auth/', include('base_modules.user_manager.headless_wrapper_urls')),
        path('api/v1/accounts/', include('allauth.urls')),
        path('api/v1/accounts/_allauth/', include('allauth.headless.urls')),
        path('api/v1/users/', include('base_modules.user_manager.urls')),
        path('api/attachments/', include(('base_modules.attachment.urls', 'attachment'), namespace='attachment')),
        path('api/slack/', include(('base_modules.integrations.notifications.urls', 'notifications'), namespace='slack')),
        path('api/n8n/', include(('base_modules.integrations.automation.urls', 'automation'), namespace='n8n')),
        path('api/whatsapp/', include(('base_modules.integrations.messaging.urls', 'messaging'), namespace='twilio')),
    ]
