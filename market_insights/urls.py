from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('market-data', views.MarketDataViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # path('refresh/<int:watch_model_id>/', views.RefreshMarketDataView.as_view(), name='refresh_market_data'),
    # path('trends/', views.MarketTrendsView.as_view(), name='market_trends'),
]