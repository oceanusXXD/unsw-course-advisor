# backend/chatbot/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("chat_multiround/", views.chat_multiround, name="chat_multiround"),
    path('activate_license/', views.activate_license_api, name='activate_license'),
    path('get_file_key/', views.get_file_key_api, name='get_file_key'),
    path('validate_license/', views.validate_license_api, name='validate_license'),
]
