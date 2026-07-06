from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.catalog import views as catalog_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('search/', catalog_views.search_view, name='search'),
    path('catalog/', include('apps.catalog.urls', namespace='catalog')),
    path('', include('apps.leads.urls', namespace='leads')),
    path('', include('apps.home.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
