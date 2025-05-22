from django.urls import path
from .views import (
    DashboardStatsAPIView,
    ExpenseTrackingAPIView, 
    IncomeBreakdownAPIView,
    DetailedAnalyticsAPIView
)

urlpatterns = [
    path('stats/', DashboardStatsAPIView.as_view(), name='dashboard-stats'),
    path('expense-tracking/', ExpenseTrackingAPIView.as_view(), name='expense-tracking'),
    path('income-breakdown/', IncomeBreakdownAPIView.as_view(), name='income-breakdown'),
    path('detailed-analytics/', DetailedAnalyticsAPIView.as_view(), name='detailed-analytics'),
]
