from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('brands', views.BrandViewSet)
router.register('models', views.WatchModelViewSet)
router.register('watches', views.WatchViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', views.InventoryStatsView.as_view(), name='inventory_stats'),
]