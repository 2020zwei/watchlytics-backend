from django.urls import path
from .views import (
    DashboardStatsAPIView,
    ExpenseTrackingAPIView, 
    IncomeBreakdownAPIView,
    DetailedAnalyticsAPIView,
    DrilldownSoldItemsAPIView,
    ProfitAnalyticsAPIView,
    IncomeReportsAPIView
)

urlpatterns = [
    path('stats/', DashboardStatsAPIView.as_view(), name='dashboard-stats'),
    path('expense-tracking/', ExpenseTrackingAPIView.as_view(), name='expense-tracking'),
    path('income-breakdown/', IncomeBreakdownAPIView.as_view(), name='income-breakdown'),
    path('detailed-analytics/', DetailedAnalyticsAPIView.as_view(), name='detailed-analytics'),
    path('sold-items/', DrilldownSoldItemsAPIView.as_view(), name='sold-items-drilldown'),
    path('profit-analytics/', ProfitAnalyticsAPIView.as_view(), name='profit-analytics'),
    path('income-reports/', IncomeReportsAPIView.as_view(), name='income-reports'),

]
