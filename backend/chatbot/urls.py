# backend/chatbot/urls.py
from django.urls import path
from . import views,view_profile

urlpatterns = [
    path("chat_multiround/", views.chat_multiround, name="chat_multiround"),
    path("chatbot_profile/", view_profile.chatbot_profile, name="chatbot_profile"),
    path('turn/<str:turn_id>/timeline/', views.turn_timeline, name='turn_timeline'),
]
