from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import models
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import month_name
from decimal import Decimal
from decimal import Decimal, InvalidOperation
from transactions.models import TransactionHistory, TransactionItem
from django.db.models.functions import Coalesce, TruncMonth
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
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
            # Basic product statistics
            product_stats = Product.objects.filter(owner=user).aggregate(
                in_stock=Count('id', filter=Q(availability='in_stock')),
                reserved=Count('id', filter=Q(availability='reserved')),
                sold_count=Count('id', filter=Q(availability='sold'))  # Total sold count
            )
            
            # Sales data from transaction items
            sales_data = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale'
            ).aggregate(
                total_sales=Coalesce(Sum(F('quantity') * F('sale_price')), Decimal('0')),
                total_purchases=Coalesce(Sum(F('quantity') * F('purchase_price')), Decimal('0')),
                count=Count('id'),
                total_quantity_sold=Coalesce(Sum('quantity'), 0)
            )
            
            total_profit = sales_data['total_sales'] - sales_data['total_purchases']
            
            average_profit_per_unit = Decimal('0')
            if sales_data['total_quantity_sold'] > 0:
                average_profit_per_unit = total_profit / sales_data['total_quantity_sold']
            
            transaction_profit_data = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                sale_price__isnull=False,
                purchase_price__isnull=False
            ).aggregate(
                total_transaction_profit=Coalesce(
                    Sum(F('quantity') * (F('sale_price') - F('purchase_price'))), 
                    Decimal('0')
                ),
                transaction_count=Count('transaction_id', distinct=True)
            )
            
            average_profit_per_transaction = Decimal('0')
            if transaction_profit_data['transaction_count'] > 0:
                average_profit_per_transaction = (
                    transaction_profit_data['total_transaction_profit'] / 
                    transaction_profit_data['transaction_count']
                )
            
            # Alternative method if you need item-level calculation (commented out)
            """
            sold_transactions = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                sale_price__isnull=False,
                purchase_price__isnull=False
            )
            
            transaction_profits = []
            for item in sold_transactions:
                # Fixed: Added null checks to prevent errors
                if item.sale_price is not None and item.purchase_price is not None and item.quantity is not None:
                    item_profit = (item.sale_price - item.purchase_price) * item.quantity
                    transaction_profits.append(item_profit)
            
            average_profit_per_transaction = Decimal('0')
            if transaction_profits:
                average_profit_per_transaction = sum(transaction_profits) / len(transaction_profits)
            """
            
            stats_data = {
                'manage_in_stock': product_stats['in_stock'],
                'sold_amount': sales_data['total_sales'],
                'pending_sale': product_stats['reserved'],
                'total_orders': sales_data['count'],
                'total_profit': total_profit,
                'total_purchase_amount': sales_data['total_purchases'],
                
                'total_sold_count': product_stats['sold_count'],  # Drillable metric
                'total_quantity_sold': sales_data['total_quantity_sold'],  # Alternative sold count
                
                'average_profit_per_unit': float(average_profit_per_unit),
                'average_profit_per_transaction': float(average_profit_per_transaction),
                
                'profit_margin_percentage': float(
                    (total_profit / sales_data['total_sales'] * 100) 
                    if sales_data['total_sales'] > 0 else 0
                ),
                
                'inventory_summary': {
                    'in_stock': product_stats['in_stock'],
                    'reserved': product_stats['reserved'],
                    'sold': product_stats['sold_count'],
                    'total_products': product_stats['in_stock'] + product_stats['reserved'] + product_stats['sold_count']
                }
            }
            
            return Response(stats_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Could not retrieve dashboard stats: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DrilldownSoldItemsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        try:
            # Get pagination parameters from query params
            # For sold_products
            products_page = request.GET.get('products_page', 1)
            products_page_size = request.GET.get('products_page_size', 10)
            
            # For sold_transaction_items
            transactions_page = request.GET.get('transactions_page', 1)
            transactions_page_size = request.GET.get('transactions_page_size', 10)
            
            # Validate page_sizes
            try:
                products_page_size = int(products_page_size)
                if products_page_size <= 0:
                    products_page_size = 10
                if products_page_size > 100:
                    products_page_size = 100
            except (ValueError, TypeError):
                products_page_size = 10
                
            try:
                transactions_page_size = int(transactions_page_size)
                if transactions_page_size <= 0:
                    transactions_page_size = 10
                if transactions_page_size > 100:
                    transactions_page_size = 100
            except (ValueError, TypeError):
                transactions_page_size = 10
            
            # Get all sold products with detailed information (QuerySet for pagination)
            sold_products_queryset = Product.objects.filter(
                owner=user,
                availability='sold'
            ).select_related('category').values(
                'id',
                'product_id',
                'model_name',
                'category__name',
                'buying_price',
                'sold_price',
                'profit',
                'date_purchased',
                'date_sold',
                'sold_source'
            ).order_by('-date_sold')  # Order by most recent sold first
            
            products_paginator = Paginator(sold_products_queryset, products_page_size)
            
            try:
                sold_products_page = products_paginator.page(products_page)
            except PageNotAnInteger:
                sold_products_page = products_paginator.page(1)
            except EmptyPage:
                sold_products_page = products_paginator.page(products_paginator.num_pages)
            
            sold_products_with_days = []
            for product in sold_products_page:
                product_dict = dict(product)
                if product['date_purchased'] and product['date_sold']:
                    days_diff = (product['date_sold'] - product['date_purchased']).days
                    product_dict['days_in_inventory'] = days_diff
                else:
                    product_dict['days_in_inventory'] = None
                sold_products_with_days.append(product_dict)
            
            sold_transaction_items_queryset = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale'
            ).select_related('product', 'transaction').values(
                'id',
                'product__product_id',
                'product__model_name',
                'product__category__name',
                'quantity',
                'sale_price',
                'purchase_price',
                'transaction__date',
                'transaction__name_of_trade',
                'transaction__customer__name'
            ).order_by('-transaction__date')  # Order by most recent transaction first
            
            transactions_paginator = Paginator(sold_transaction_items_queryset, transactions_page_size)
            
            try:
                sold_transaction_items_page = transactions_paginator.page(transactions_page)
            except PageNotAnInteger:
                sold_transaction_items_page = transactions_paginator.page(1)
            except EmptyPage:
                sold_transaction_items_page = transactions_paginator.page(transactions_paginator.num_pages)
            
            transaction_items_with_profit = []
            for item in sold_transaction_items_page:
                if item['sale_price'] and item['purchase_price']:
                    profit = (item['sale_price'] - item['purchase_price']) * item['quantity']
                else:
                    profit = 0.0
                
                renamed_item = {
                    'id': item['id'],
                    'reference_number': item['product__product_id'],
                    'Model': item['product__model_name'],
                    'brand': item['product__category__name'],
                    'quantity': item['quantity'],
                    'sale_price': item['sale_price'],
                    'purchase_price': item['purchase_price'],
                    'transaction_date': item['transaction__date'],
                    'transaction_name': item['transaction__name_of_trade'],
                    'customer_name': item['transaction__customer__name'],
                    'profit': float(profit)
                }
                transaction_items_with_profit.append(renamed_item)
            
            response_data = {
                'sold_products': {
                    'count': products_paginator.count,  # Total number of sold products
                    'total_pages': products_paginator.num_pages,
                    'current_page': sold_products_page.number,
                    'page_size': products_page_size,
                    'has_next': sold_products_page.has_next(),
                    'has_previous': sold_products_page.has_previous(),
                    'next_page': sold_products_page.next_page_number() if sold_products_page.has_next() else None,
                    'previous_page': sold_products_page.previous_page_number() if sold_products_page.has_previous() else None,
                    'results': sold_products_with_days
                },
                'sold_transaction_items': {
                    'count': transactions_paginator.count,  # Total number of transaction items
                    'total_pages': transactions_paginator.num_pages,
                    'current_page': sold_transaction_items_page.number,
                    'page_size': transactions_page_size,
                    'has_next': sold_transaction_items_page.has_next(),
                    'has_previous': sold_transaction_items_page.has_previous(),
                    'next_page': sold_transaction_items_page.next_page_number() if sold_transaction_items_page.has_next() else None,
                    'previous_page': sold_transaction_items_page.previous_page_number() if sold_transaction_items_page.has_previous() else None,
                    'results': transaction_items_with_profit
                },
                'summary': {
                    'total_sold_value': sum(
                        float(item.get('sale_price', 0) or 0) * item.get('quantity', 1) 
                        for item in transaction_items_with_profit
                    ),
                    'total_profit': sum(
                        item.get('profit', 0) for item in transaction_items_with_profit
                    )
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Could not retrieve sold items details: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ProfitAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        try:
            # Profit breakdown by category
            category_profits = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                sale_price__isnull=False,
                purchase_price__isnull=False
            ).values(
                'product__category__name'
            ).annotate(
                total_profit=Sum(
                    (F('sale_price') - F('purchase_price')) * F('quantity')
                ),
                avg_profit=Avg(
                    (F('sale_price') - F('purchase_price')) * F('quantity')
                ),
                total_sales=Sum(F('sale_price') * F('quantity')),
                count=Count('id')
            ).order_by('-total_profit')
            
            # Monthly profit trend using Django's TruncMonth
            monthly_profits = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                sale_price__isnull=False,
                purchase_price__isnull=False
            ).annotate(
                month=TruncMonth('transaction__date')
            ).values('month').annotate(
                total_profit=Sum(
                    (F('sale_price') - F('purchase_price')) * F('quantity')
                ),
                total_sales=Sum(F('sale_price') * F('quantity')),
                count=Count('id')
            ).order_by('month')
            
            # Top performing products
            top_products = TransactionItem.objects.filter(
                transaction__user=user,
                transaction__transaction_type='sale',
                sale_price__isnull=False,
                purchase_price__isnull=False
            ).values(
                'product__product_id',
                'product__model_name'
            ).annotate(
                total_profit=Sum(
                    (F('sale_price') - F('purchase_price')) * F('quantity')
                ),
                total_sales=Sum(F('sale_price') * F('quantity')),
                quantity_sold=Sum('quantity')
            ).order_by('-total_profit')[:10]
            
            # Convert monthly profits to proper format
            monthly_profits_formatted = []
            for item in monthly_profits:
                monthly_profits_formatted.append({
                    'month': item['month'].strftime('%Y-%m') if item['month'] else None,
                    'total_profit': float(item['total_profit']) if item['total_profit'] else 0.0,
                    'total_sales': float(item['total_sales']) if item['total_sales'] else 0.0,
                    'count': item['count']
                })
            
            response_data = {
                'category_analysis': list(category_profits),
                'monthly_trends': monthly_profits_formatted,
                'top_performing_products': list(top_products),
                'overall_metrics': {
                    'total_categories': len(category_profits),
                    'best_category': category_profits[0]['product__category__name'] if category_profits else None,
                    'best_month': max(monthly_profits_formatted, key=lambda x: x['total_profit'])['month'] if monthly_profits_formatted else None
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Could not retrieve profit analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ExpenseTrackingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        period_type = request.query_params.get('tracking', 'monthly').lower()
        
        if period_type not in ['monthly', 'quarterly', 'yearly']:
            return Response(
                {'error': 'Invalid period type. Use: monthly, quarterly, or yearly'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        today = timezone.now().date()
        period_data = []
        
        if period_type == 'monthly':
            period_data = self._get_monthly_data(user, today)
        elif period_type == 'quarterly':
            period_data = self._get_quarterly_data(user, today)
        elif period_type == 'yearly':
            period_data = self._get_yearly_data(user, today)
        
        return Response(period_data, status=status.HTTP_200_OK)
    
    def _get_monthly_data(self, user, today):
        """Get 6 months of data"""
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
            
            data = self._calculate_period_data(user, month_start, next_month_start)
            data['period'] = f"{month_name[month_start.month]} {month_start.year}"
            monthly_data.append(data)
        
        monthly_data.reverse()
        return monthly_data
    
    def _get_quarterly_data(self, user, today):
        quarterly_data = []
        
        current_quarter = (today.month - 1) // 3 + 1
        current_year = today.year
        
        for i in range(4):
            quarter = current_quarter - i
            year = current_year
            
            while quarter < 1:
                quarter += 4
                year -= 1
            
            quarter_start_month = (quarter - 1) * 3 + 1
            quarter_start = today.replace(year=year, month=quarter_start_month, day=1)
            
            if quarter == 4:
                quarter_end = today.replace(year=year + 1, month=1, day=1)
            else:
                quarter_end = today.replace(year=year, month=quarter_start_month + 3, day=1)
            
            data = self._calculate_period_data(user, quarter_start, quarter_end)
            data['period'] = f"Q{quarter} {year}"
            quarterly_data.append(data)
        
        quarterly_data.reverse()
        return quarterly_data
    
    def _get_yearly_data(self, user, today):
        yearly_data = []
        
        for i in range(3):
            year = today.year - i
            year_start = today.replace(year=year, month=1, day=1)
            year_end = today.replace(year=year + 1, month=1, day=1)
            
            data = self._calculate_period_data(user, year_start, year_end)
            data['period'] = str(year)
            yearly_data.append(data)
        
        yearly_data.reverse()
        return yearly_data
    
    def _calculate_period_data(self, user, start_date, end_date):
        sales_amount = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale',
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(
            total=Sum('sale_price')
        )['total'] or Decimal('0')
        
        sales_items = TransactionItem.objects.filter(
            transaction__user=user,
            transaction__transaction_type='sale',
            transaction__date__gte=start_date,
            transaction__date__lt=end_date,
            sale_price__isnull=False
        ).aggregate(
            total=Sum(F('quantity') * F('sale_price'))
        )['total'] or Decimal('0')
        
        sales_amount = max(sales_amount, sales_items)
        
        purchase_amount = TransactionHistory.objects.filter(
            user=user,
            transaction_type='purchase',
            date__gte=start_date,
            date__lt=end_date
        ).aggregate(
            total=Sum('purchase_price')
        )['total'] or Decimal('0')
        
        purchase_items = TransactionItem.objects.filter(
            transaction__user=user,
            transaction__transaction_type='purchase',
            transaction__date__gte=start_date,
            transaction__date__lt=end_date,
            purchase_price__isnull=False
        ).aggregate(
            total=Sum(F('quantity') * F('purchase_price'))
        )['total'] or Decimal('0')
        
        purchase_amount = max(purchase_amount, purchase_items)
        
        total_expenses = Decimal('0')
        
        product_expenses = Product.objects.filter(
            owner=user,
            date_purchased__gte=start_date,
            date_purchased__lt=end_date
        ).aggregate(
            shipping=Sum('shipping_price') or Decimal('0'),
            repairs=Sum('repair_cost') or Decimal('0'),
            fees=Sum('fees') or Decimal('0'),
            commission=Sum('commission') or Decimal('0')
        )
        
        product_total_expenses = (
            (product_expenses['shipping'] or Decimal('0')) +
            (product_expenses['repairs'] or Decimal('0')) +
            (product_expenses['fees'] or Decimal('0')) +
            (product_expenses['commission'] or Decimal('0'))
        )
        
        # 2. Expenses from TransactionHistory.expenses JSONField
        transactions_with_expenses = TransactionHistory.objects.filter(
            user=user,
            date__gte=start_date,
            date__lt=end_date
        ).exclude(expenses={})
        
        transaction_expenses = Decimal('0')
        for transaction in transactions_with_expenses:
            if transaction.expenses:
                for expense_type, amount in transaction.expenses.items():
                    try:
                        transaction_expenses += Decimal(str(amount))
                    except (InvalidOperation, ValueError, TypeError):
                        continue
        
        total_expenses = product_total_expenses + transaction_expenses
        
        return {
            'sales': float(sales_amount),
            'purchases': float(purchase_amount),
            'expenses': float(total_expenses)
        }
    

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
    
    def get_filtered_data(self, user, segment_type, year_start, year_end):
        """Get detailed data based on segment type for filtering"""
        try:
            if segment_type == 'actual':
                # Get actual transactions
                transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__range=(year_start, year_end)
                ).values('id', 'sale_price', 'date', 'product_name')
                
                transaction_items = TransactionItem.objects.filter(
                    transaction__user=user,
                    transaction__transaction_type='sale',
                    transaction__date__range=(year_start, year_end)
                ).select_related('transaction', 'product').values(
                    'transaction__id', 'quantity', 'sale_price', 
                    'transaction__date', 'product__name'
                )
                
                return {
                    'transactions': list(transactions),
                    'transaction_items': list(transaction_items)
                }
                
            elif segment_type == 'pending':
                # Get pending/reserved products
                products = Product.objects.filter(
                    owner=user,
                    availability='reserved'
                ).values('id', 'name', 'website_price', 'sold_price', 'msrp')
                
                return {'products': list(products)}
                
            elif segment_type == 'remaining':
                # Calculate remaining to target
                actual_income = self.get_actual_income(user, year_start, year_end)
                pending_income = self.get_pending_income(user)
                target = self.calculate_target(actual_income, pending_income, user)
                remaining = target - actual_income - pending_income
                
                # Get products that could contribute to remaining target
                available_products = Product.objects.filter(
                    owner=user,
                    availability__in=['available', 'in_stock']
                ).values('id', 'name', 'website_price', 'sold_price', 'msrp')
                
                return {
                    'remaining_amount': float(remaining),
                    'available_products': list(available_products)
                }
                
        except Exception as e:
            return {'error': str(e)}
    
    def get(self, request):
        user = request.user
        segment_filter = request.GET.get('segment')  # Get segment filter parameter
        
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
                'progress': float(actual_income / target) if target > 0 else 0,
                'segments': {
                    'actual': {
                        'value': float(actual_income),
                        'percentage': float(actual_income / target * 100) if target > 0 else 0,
                        'label': 'Actual Income',
                        'color': '#10B981'  # Green
                    },
                    'pending': {
                        'value': float(pending_income),
                        'percentage': float(pending_income / target * 100) if target > 0 else 0,
                        'label': 'Pending Income',
                        'color': '#F59E0B'  # Amber
                    },
                    'remaining': {
                        'value': float(max(0, target - actual_income - pending_income)),
                        'percentage': float(max(0, target - actual_income - pending_income) / target * 100) if target > 0 else 0,
                        'label': 'Remaining to Target',
                        'color': '#EF4444'  # Red
                    }
                }
            }
            
            # If segment filter is provided, include filtered data
            if segment_filter and segment_filter in ['actual', 'pending', 'remaining']:
                breakdown_data['filtered_data'] = self.get_filtered_data(
                    user, segment_filter, year_start, year_end
                )
                breakdown_data['active_filter'] = segment_filter
            
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
    
class IncomeReportsAPIView(APIView):
    """API for income reports with clickable segments showing detailed data"""
    permission_classes = [IsAuthenticated]
    
    def get_date_range(self, request):
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from and date_to:
            year_start = datetime.strptime(date_from, '%Y-%m-%d').date()
            year_end = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            current_year = timezone.now().year
            year_start = datetime(current_year, 1, 1).date()
            year_end = datetime(current_year, 12, 31).date()
            
        return year_start, year_end
    
    def get_actual_income_data(self, user, year_start, year_end):
        """Get detailed actual income data"""
        transactions = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale',
            date__range=(year_start, year_end)
        ).select_related('customer').values(
            'id', 'date', 'sale_price', 'name_of_trade',
            customer_name=F('customer__name')
        ).order_by('-date')
        
        monthly_summary = list(
            TransactionHistory.objects.filter(
                user=user,
                transaction_type='sale',
                date__range=(year_start, year_end)
            ).extra(
                select={'month': 'EXTRACT(month FROM date)'}
            ).values('month').annotate(
                total=Sum('sale_price'),
                count=Count('id')
            ).order_by('month')
        )
        
        return {
            'transactions': list(transactions),
            'monthly_summary': monthly_summary
        }
    
    def get_pending_income_data(self, user):
        """Get detailed pending income data"""
        products = Product.objects.filter(
            owner=user,
            availability='reserved'
        ).values(
            'id', 'model_name', 'website_price', 'sold_price',
            'msrp', 'category_id', 'condition'
        ).order_by('-msrp')
        
        return {
            'products': list(products)
        }
    
    def get_remaining_target_data(self, user, year_start, year_end):
        """Get detailed data for remaining target"""
        actual_income = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale',
            date__range=(year_start, year_end)
        ).aggregate(total=Sum('sale_price'))['total'] or Decimal('0')
        
        pending_income = Product.objects.filter(
            owner=user,
            availability='reserved'
        ).aggregate(total=Sum('sold_price'))['total'] or Decimal('0')
        
        target = (actual_income + pending_income) * Decimal('1.2')
        remaining = max(Decimal('0'), target - actual_income - pending_income)
        
        available_products = Product.objects.filter(
            owner=user,
            availability__in=['available', 'in_stock']
        ).annotate(
            brand=F('category__name'),
            reference_number=F('product_id')
        ).values(
            'id',
            'brand',
            'model_name',
            'reference_number',
            'quantity',
            'website_price',
            'msrp'
        ).order_by('-msrp')
        
        return {
            'remaining_amount': float(remaining),
            'target': float(target),
            'available_products': list(available_products)
        }
    
    def get(self, request):
        user = request.user
        segment_type = request.GET.get('segment', None)  # 'actual', 'pending', or 'remaining'
        
        try:
            year_start, year_end = self.get_date_range(request)
            response_data = {}
            
            if not segment_type:
                # Return summary data if no segment specified
                actual_income = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__range=(year_start, year_end)
                ).aggregate(total=Sum('sale_price'))['total'] or Decimal('0')
                
                pending_income = Product.objects.filter(
                    owner=user,
                    availability='reserved'
                ).aggregate(total=Sum('sold_price'))['total'] or Decimal('0')
                
                target = (actual_income + pending_income) * Decimal('1.2')
                
                response_data = {
                    'summary': {
                        'actual_income': float(actual_income),
                        'pending_income': float(pending_income),
                        'target': float(target),
                        'progress': float(actual_income / target) if target > 0 else 0,
                        'year': year_start.year
                    }
                }
            else:
                # Return detailed data for the requested segment
                if segment_type == 'actual':
                    response_data = self.get_actual_income_data(user, year_start, year_end)
                elif segment_type == 'pending':
                    response_data = self.get_pending_income_data(user)
                elif segment_type == 'remaining':
                    response_data = self.get_remaining_target_data(user, year_start, year_end)
                else:
                    return Response(
                        {'error': 'Invalid segment type'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {
                    'error': 'Could not generate reports',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )