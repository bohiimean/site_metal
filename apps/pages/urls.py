from django.urls import path

from . import views

app_name = 'pages'

urlpatterns = [
    path('novosti/', views.news_list, name='news_list'),
    path('novosti/<slug:slug>/', views.news_detail, name='news_detail'),
    # Catch-all для статических страниц — подключается последним в config.urls
    path('<slug:slug>/', views.page_detail, name='page_detail'),
]
