from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('plans', views.PlanViewSet)
# router.register('subscriptions', views.SubscriptionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    # path('webhook/', views.StripeWebhookView.as_view(), name='webhook'),
    # path('manage/', views.ManageSubscriptionView.as_view(), name='manage_subscription'),
]