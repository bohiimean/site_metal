from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('',          views.catalog_index,    name='index'),
    path('<slug:slug>/', views.catalog_slug_view, name='detail'),
]
