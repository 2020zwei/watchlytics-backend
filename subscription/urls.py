from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import StripePayment, StripeWebhook, GetSubscriptionDetails, CardManagementAPIView, CardOperationsAPIView

from . import views

urlpatterns = [
    path('plans/', views.PlanListAPIView.as_view(), name='plan-list'),
    path('subscribe/', StripePayment.as_view(), name='stripe-subscribe'),
    path('plans/<int:pk>/', views.PlanDetailAPIView.as_view(), name='plan-detail'),

    path('subscription/', views.UserSubscriptionAPIView.as_view(), name='user-subscription'),
    path('subscription/create/', views.CreateSubscriptionAPIView.as_view(), name='create-subscription'),
    path('subscription/update/', views.UpdateSubscriptionAPIView.as_view(), name='update-subscription'),
    
    path('webhook/stripe/', StripeWebhook.as_view(), name='stripe-webhook'),
    path('subscription/details/', GetSubscriptionDetails.as_view(), name='subscription-details'),
    path('v1/cards/', CardManagementAPIView.as_view(), name='card-management'),
    path('v1/cards/<int:card_id>/set_default/', CardOperationsAPIView.as_view(), name='set-default-card'),
    path('v1/cards/<int:card_id>/', CardOperationsAPIView.as_view(), name='delete-card'),

]