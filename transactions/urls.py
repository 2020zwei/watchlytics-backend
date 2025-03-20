from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('transactions', views.TransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # path('stats/', views.TransactionStatsView.as_view(), name='transaction_stats'),
]
