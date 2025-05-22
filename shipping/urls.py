from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'senders', views.SenderAddressViewSet)
router.register(r'recipients', views.RecipientAddressViewSet)
router.register(r'shipments', views.ShipmentViewSet)

# Define the URL patterns
urlpatterns = [
    # Include all router-generated URLs
    path('', include(router.urls)),
    
    # Custom endpoints
    path('calculate-shipping/', views.ShippingCalculationView.as_view(), name='calculate-shipping'),
    path('config/', views.ShippingConfigView.as_view(), name='shipping-config'),
    # path('config/test-connection/', views.ShippingConfigView.as_view(actions={'get': 'test_connection'}), name='test-connection'),
    
    # Additional non-viewset actions
    path('senders/sync-from-ifs/', views.SenderAddressViewSet.as_view({'get': 'sync_from_ifs'}), name='sync-senders'),
    path('recipients/sync-from-ifs/', views.RecipientAddressViewSet.as_view({'get': 'sync_from_ifs'}), name='sync-recipients'),
    path('recipients/verify/', views.RecipientAddressViewSet.as_view({'post': 'verify'}), name='verify-recipient'),
    path('recipients/get-by-zipcode/', views.RecipientAddressViewSet.as_view({'get': 'get_by_zipcode'}), name='get-by-zipcode'),
]