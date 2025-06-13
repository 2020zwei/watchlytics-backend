# customers/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, CustomerTransactionsAPIView, CustomerDashboardMetricsAPIView, CustomerOrderListView, CustomerBulkSelectView, CustomerBulkActionsView

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')

urlpatterns = [
    path('', include(router.urls)),
    path('customers/<int:customer_id>/transactions/', CustomerTransactionsAPIView.as_view(),name='customer-transactions'),
    path('dashboard-metrics/', CustomerDashboardMetricsAPIView.as_view(), name='customer-dashboard-metrics'),
    path('customers/<int:customer_id>/orders/', CustomerOrderListView.as_view(), name='customer-orders'),
    path('customers/bulk/select/', CustomerBulkSelectView.as_view(), name='customer-bulk-select'),
    path('customers/bulk/actions/', CustomerBulkActionsView.as_view(), name='customer-bulk-actions'),
]