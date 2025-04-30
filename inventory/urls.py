from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, DashboardStatsView, ProductCSVUploadAPIView

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('upload-products/', ProductCSVUploadAPIView.as_view(), name='upload-products'),
]