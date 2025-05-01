from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TransactionHistoryViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionHistoryViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
]
