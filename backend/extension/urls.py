# backend/extension/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('start-extension/', views.launch_and_check_extension, name='start_extension'),
]
