from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard summary statistics
    path('stats/', views.DashboardAPIView.as_view(), name='dashboard_stats'),
    
    # Best selling products
    path('best-selling/', views.BestSellingProductsAPIView.as_view(), name='best_selling_products'),
    
    # Expense reports
    path('expenses/', views.ExpenseReportAPIView.as_view(), name='expense_report'),
    
    # Stock aging analysis
    path('stock-aging/', views.StockAgingAPIView.as_view(), name='stock_aging'),
    path('stock-aging/<str:stock_ref>/', views.StockDetailAPIView.as_view(), name='stock-detail'),

    # Market price comparison
    path('market-comparison/', views.MarketComparisonAPIView.as_view(), name='market_comparison'),
    
    # Monthly profit and loss
    path('monthly-profit/', views.MonthlyProfitAPIView.as_view(), name='monthly_profit'),
    
    # User performance metrics
    path('user-metrics/', views.UserSpecificReportAPIView.as_view(), name='user_metrics'),
    
    # Stock turnover analysis
    path('stock-turnover/', views.StockTurnoverAPIView.as_view(), name='stock_turnover'),
    
    # Live inventory data
    path('inventory/', views.LiveInventoryAPIView.as_view(), name='live_inventory'),
    
    # Purchase and sales report
    path('purchase-sales/', views.PurchaseSalesReportAPIView.as_view(), name='purchase_sales_report'),
]