from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import month_name
from decimal import Decimal
from transactions.models import TransactionHistory, TransactionItem
from inventory.models import Product
from .serializers import (
    DashboardStatsSerializer, 
    ExpenseTrackingSerializer, 
    IncomeBreakdownSerializer
)


class DashboardStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        manage_in_stock = Product.objects.filter(
            owner=user, 
            availability='in_stock'
        ).count()
        
        sold_amount = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale'
        ).aggregate(
            total=Sum('sale_price')
        )['total'] or Decimal('0')
        
        sold_amount_items = TransactionItem.objects.filter(
            transaction__user=user,
            transaction__transaction_type='sale',
            sale_price__isnull=False
        ).aggregate(
            total=Sum(F('quantity') * F('sale_price'))
        )['total'] or Decimal('0')
        
        sold_amount = max(sold_amount, sold_amount_items)
        
        pending_sale = Product.objects.filter(
            owner=user,
            availability='reserved'
        ).count()
        
        total_orders = TransactionHistory.objects.filter(user=user).count()
        
        stats_data = {
            'manage_in_stock': manage_in_stock,
            'sold_amount': sold_amount,
            'pending_sale': pending_sale,
            'total_orders': total_orders
        }
        
        return Response(stats_data, status=status.HTTP_200_OK)


class ExpenseTrackingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        today = timezone.now().date()
        six_months_ago = today - timedelta(days=180)
        
        monthly_data = []
        
        for i in range(6):
            month_date = today.replace(day=1) - timedelta(days=i*30)
            month_start = month_date.replace(day=1)
            
            if month_start.month == 12:
                next_month_start = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month_start = month_start.replace(month=month_start.month + 1)
            
            sales_amount = TransactionHistory.objects.filter(
                user=user,
                transaction_type='sale',
                date__gte=month_start,
                date__lt=next_month_start
            ).aggregate(
                total=Sum('sale_price')
            )['total'] or Decimal('0')
            
            sales_items = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                transaction__date__gte=month_start,
                transaction__date__lt=next_month_start,
                sale_price__isnull=False
            ).aggregate(
                total=Sum(F('quantity') * F('sale_price'))
            )['total'] or Decimal('0')
            
            sales_amount = max(sales_amount, sales_items)
            
            purchase_amount = TransactionHistory.objects.filter(
                user=user,
                transaction_type='purchase',
                date__gte=month_start,
                date__lt=next_month_start
            ).aggregate(
                total=Sum('purchase_price')
            )['total'] or Decimal('0')
            
            purchase_items = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='purchase',
                transaction__date__gte=month_start,
                transaction__date__lt=next_month_start,
                purchase_price__isnull=False
            ).aggregate(
                total=Sum(F('quantity') * F('purchase_price'))
            )['total'] or Decimal('0')
            
            purchase_amount = max(purchase_amount, purchase_items)
            
            monthly_data.append({
                'month': f"{month_name[month_start.month]} {month_start.year}",
                'sales': sales_amount,
                'purchases': purchase_amount
            })
        
        monthly_data.reverse()
        
        return Response(monthly_data, status=status.HTTP_200_OK)


class IncomeBreakdownAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        current_year = timezone.now().year
        year_start = datetime(current_year, 1, 1).date()
        year_end = datetime(current_year, 12, 31).date()
        
        actual_income = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale',
            date__gte=year_start,
            date__lte=year_end
        ).aggregate(
            total=Sum('sale_price')
        )['total'] or Decimal('0')
        
        income_items = TransactionItem.objects.filter(
            transaction__user=user,
            transaction__transaction_type='sale',
            transaction__date__gte=year_start,
            transaction__date__lte=year_end,
            sale_price__isnull=False
        ).aggregate(
            total=Sum(F('quantity') * F('sale_price'))
        )['total'] or Decimal('0')
        
        actual_income = max(actual_income, income_items)
        
        pending_income = Product.objects.filter(
            owner=user,
            availability='reserved',
            website_price__isnull=False
        ).aggregate(
            total=Sum('website_price')
        )['total'] or Decimal('0')
        
        if pending_income == 0:
            pending_income = Product.objects.filter(
                owner=user,
                availability='reserved'
            ).aggregate(
                total=Sum('sold_price')
            )['total'] or Decimal('0')
            
            if pending_income == 0:
                pending_income = Product.objects.filter(
                    owner=user,
                    availability='reserved'
                ).aggregate(
                    total=Sum('msrp')
                )['total'] or Decimal('0')
        
        target = (actual_income + pending_income) * Decimal('1.2')
        
        total_msrp = Product.objects.filter(
            owner=user,
            msrp__isnull=False
        ).aggregate(
            total=Sum('msrp')
        )['total'] or Decimal('0')
        
        if total_msrp > target:
            target = total_msrp
        
        breakdown_data = {
            'target': target,
            'income': actual_income,
            'pending': pending_income
        }
        
        return Response(breakdown_data, status=status.HTTP_200_OK)


class DetailedAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        total_products = Product.objects.filter(owner=user).count()
        
        inventory_age = {
            'less_than_30': Product.objects.filter(
                owner=user,
                availability='in_stock'
            ).filter(
                date_purchased__gte=timezone.now() - timedelta(days=30)
            ).count(),
            '30_to_60': Product.objects.filter(
                owner=user,
                availability='in_stock',
                date_purchased__gte=timezone.now() - timedelta(days=60),
                date_purchased__lt=timezone.now() - timedelta(days=30)
            ).count(),
            '60_to_90': Product.objects.filter(
                owner=user,
                availability='in_stock',
                date_purchased__gte=timezone.now() - timedelta(days=90),
                date_purchased__lt=timezone.now() - timedelta(days=60)
            ).count(),
            'more_than_90': Product.objects.filter(
                owner=user,
                availability='in_stock',
                date_purchased__lt=timezone.now() - timedelta(days=90)
            ).count()
        }
        
        total_profit = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale'
        ).aggregate(
            total_sales=Sum('sale_price'),
            total_purchases=Sum('purchase_price')
        )
        
        profit = Decimal('0')
        if total_profit['total_sales'] and total_profit['total_purchases']:
            profit = total_profit['total_sales'] - total_profit['total_purchases']
        
        # Category breakdown
        category_breakdown = Product.objects.filter(
            owner=user
        ).values('category__name').annotate(
            count=Count('id'),
            total_value=Sum('buying_price')
        ).order_by('-count')
        
        analytics_data = {
            'total_products': total_products,
            'inventory_age_breakdown': inventory_age,
            'total_profit': profit,
            'category_breakdown': list(category_breakdown),
            'average_profit_per_sale': profit / max(TransactionHistory.objects.filter(
                user=user, transaction_type='sale'
            ).count(), 1)
        }
        
        return Response(analytics_data, status=status.HTTP_200_OK)