from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

urlpatterns = [
    path('plans/', views.PlanListAPIView.as_view(), name='plan-list'),
    path('plans/<int:pk>/', views.PlanDetailAPIView.as_view(), name='plan-detail'),

    path('subscription/', views.UserSubscriptionAPIView.as_view(), name='user-subscription'),
    path('subscription/create/', views.CreateSubscriptionAPIView.as_view(), name='create-subscription'),
    path('subscription/update/', views.UpdateSubscriptionAPIView.as_view(), name='update-subscription'),
]