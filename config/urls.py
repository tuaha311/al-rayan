"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^_next/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static/_next'}),
    re_path(r'^images/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static/images'}),
    re_path(r'^videos/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static/videos'}),
    # The Al Rayan storefront owns the site root. The legacy XECOTech landing
    # (home app) is kept in the repo but unlinked from routing.
    path('', include('store.urls')),
]

# Serve user-uploaded media files during development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
