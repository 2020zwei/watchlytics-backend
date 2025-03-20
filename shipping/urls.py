from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('shipments', views.ShipmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # path('calculate/', views.ShippingCalculatorView.as_view(), name='shipping_calculator'),
    # path('generate-label/<int:transaction_id>/', views.GenerateShippingLabelView.as_view(), name='generate_label'),
    # path('track/<str:tracking_number>/', views.TrackShipmentView.as_view(), name='track_shipment'),
]