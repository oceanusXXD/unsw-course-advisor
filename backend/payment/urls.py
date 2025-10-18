# backend/extension/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('start-create_checkout_session/', views.create_checkout_session, name='create_checkout_session'),
    path('stripe_webhook/', views.stripe_webhook, name='stripe_webhook'),
]
