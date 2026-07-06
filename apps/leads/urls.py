from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('leads/submit/', views.submit_cart, name='submit_cart'),
    path('leads/callback/', views.submit_callback, name='submit_callback'),
]
