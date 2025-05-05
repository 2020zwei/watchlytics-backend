from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MarketDataViewSet

router = DefaultRouter()
router.register(r'market-data', MarketDataViewSet)

urlpatterns = [
    path('/', include(router.urls)),
    path('/market-comparison/', 
         MarketDataViewSet.as_view({'get': 'market_comparison'}), 
         name='market-comparison'),
]