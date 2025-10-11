# backend/chatbot/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.chat, name="chat"),
    path("chat_multi/", views.chat_multiround, name="chat_multi"),
]

