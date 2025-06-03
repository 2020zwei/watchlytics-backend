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
from django.db.models.functions import Coalesce
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
        
        try:
            product_stats = Product.objects.filter(owner=user).aggregate(
                in_stock=Count('id', filter=Q(availability='in_stock')),
                reserved=Count('id', filter=Q(availability='reserved'))
            )
            
            sales_data = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale'
            ).aggregate(
                total_sales=Coalesce(Sum(F('quantity') * F('sale_price')), Decimal('0')),
                total_purchases=Coalesce(Sum(F('quantity') * F('purchase_price')), Decimal('0')),
                count=Count('id')
            )
            
            stats_data = {
                'manage_in_stock': product_stats['in_stock'],
                'sold_amount': sales_data['total_sales'],
                'pending_sale': product_stats['reserved'],
                'total_orders': sales_data['count'],
                'total_profit': sales_data['total_sales'] - sales_data['total_purchases'],
                'total_purchase_amount': sales_data['total_purchases']
            }
            
            return Response(stats_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Could not retrieve dashboard stats'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExpenseTrackingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        
        monthly_data = []
        
        for i in range(6):
            month_year = today.year
            month_num = today.month - i
            while month_num < 1:
                month_num += 12
                month_year -= 1
            
            month_start = current_month_start.replace(year=month_year, month=month_num)
            
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
                'sales': float(sales_amount),
                'purchases': float(purchase_amount)
            })
        
        # Reverse to show oldest first
        monthly_data.reverse()
        
        return Response(monthly_data, status=status.HTTP_200_OK)


class IncomeBreakdownAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_actual_income(self, user, year_start, year_end):
        try:
            history_income = TransactionHistory.objects.filter(
                user=user,
                transaction_type='sale',
                date__range=(year_start, year_end)
            ).aggregate(
                total=Sum('sale_price')
            )['total'] or Decimal('0')
            
            items_income = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                transaction__date__range=(year_start, year_end)
            ).aggregate(
                total=Sum(F('quantity') * F('sale_price'))
            )['total'] or Decimal('0')
            
            return max(history_income, items_income)
        except Exception as e:
            return Decimal('0')
    
    def get_pending_income(self, user):
        try:
            price_fields = ['website_price', 'sold_price', 'msrp']
            
            for field in price_fields:
                result = Product.objects.filter(
                    owner=user,
                    availability='reserved',
                    **{f"{field}__isnull": False}
                ).aggregate(
                    total=Sum(field)
                )
                if result['total']:
                    return result['total']
            
            return Decimal('0')
        except Exception as e:
            return Decimal('0')
    
    def calculate_target(self, actual_income, pending_income, user):
        try:
            base_target = (actual_income + pending_income) * Decimal('1.2')
            
            total_msrp = Product.objects.filter(
                owner=user,
                msrp__isnull=False
            ).aggregate(
                total=Sum('msrp')
            )['total'] or Decimal('0')
            
            return max(base_target, total_msrp)
        except Exception as e:
            return Decimal('0')
    
    def get(self, request):
        user = request.user
        
        try:
            current_year = timezone.now().year
            year_start = datetime(current_year, 1, 1).date()
            year_end = datetime(current_year, 12, 31).date()
            
            actual_income = self.get_actual_income(user, year_start, year_end)
            pending_income = self.get_pending_income(user)
            target = self.calculate_target(actual_income, pending_income, user)
            
            breakdown_data = {
                'target': float(target),
                'income': float(actual_income),
                'pending': float(pending_income),
                'year': current_year,
                'progress': float(actual_income / target) if target > 0 else 0
            }
            
            return Response(breakdown_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {
                    'error': 'Could not calculate income breakdown',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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