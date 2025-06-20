from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Count, F, Q, Avg, Case, When, Value, IntegerField, DecimalField, FloatField
from django.db.models import Q, Case, When, Value, CharField, ExpressionWrapper, F, IntegerField, Func
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek, Coalesce
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
from inventory.models import Product, Category
from .serializers import ProductSerializer, CategorySerializer, DashboardStatsSerializer
import calendar
from django.db.models.functions import Cast
from django.db.models import CharField, Case, When, Value, Q
from transactions.models import TransactionHistory, TransactionItem
from rest_framework.permissions import AllowAny, IsAuthenticated
import logging
logger = logging.getLogger(__name__)


class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class DashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get all sale transactions for the user
        sale_transactions = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale'
        ).prefetch_related('transaction_items')
        
        # Calculate total profit, revenue and sales from transactions
        total_profit = Decimal('0')
        revenue = Decimal('0')
        sales_count = 0
        net_sales_value = Decimal('0')
        
        for transaction in sale_transactions:
            total_profit += transaction.profit or Decimal('0')
            revenue += transaction.total_sale_price or Decimal('0')
            net_sales_value += transaction.total_sale_price or Decimal('0')
            sales_count += transaction.transaction_items.count()
        
        # Calculate net purchase value from all products
        net_purchase_value = Product.objects.filter(owner=user).aggregate(
            total=Coalesce(Sum('buying_price'), Decimal('0'), output_field=DecimalField())
        )['total'] or Decimal('0')
        
        # Month over month profit
        current_month = timezone.now().month
        current_year = timezone.now().year
        
        current_month_profit = Decimal('0')
        current_month_sales = sale_transactions.filter(
            date__month=current_month,
            date__year=current_year
        )
        for transaction in current_month_sales:
            current_month_profit += transaction.profit or Decimal('0')
        
        previous_month = (timezone.now().replace(day=1) - timedelta(days=1))
        previous_month_number = previous_month.month
        previous_month_year = previous_month.year
        
        previous_month_profit = Decimal('0')
        previous_month_sales = sale_transactions.filter(
            date__month=previous_month_number,
            date__year=previous_month_year
        )
        for transaction in previous_month_sales:
            previous_month_profit += transaction.profit or Decimal('0')
        
        mom_profit = current_month_profit - previous_month_profit
        
        # Year over year profit
        last_year = current_year - 1
        
        current_year_profit = Decimal('0')
        current_year_sales = sale_transactions.filter(
            date__year=current_year
        )
        for transaction in current_year_sales:
            current_year_profit += transaction.profit or Decimal('0')
        
        previous_year_profit = Decimal('0')
        previous_year_sales = sale_transactions.filter(
            date__year=last_year
        )
        for transaction in previous_year_sales:
            previous_year_profit += transaction.profit or Decimal('0')
        
        yoy_profit = current_year_profit - previous_year_profit
        
        # Return formatted data
        return Response({
            'total_profit': float(total_profit),
            'revenue': float(revenue),
            'sales': sales_count,
            'net_purchase_value': float(net_purchase_value),
            'net_sales_value': float(net_sales_value),
            'mom_profit': float(mom_profit),
            'yoy_profit': float(yoy_profit)
        })


class BestSellingProductsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request):
        user = request.user
        
        # Get all sale transactions for the user
        sale_transactions = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale'
        ).prefetch_related('transaction_items__product')
        
        # Create a dictionary to aggregate product sales
        product_sales = {}
        
        for transaction in sale_transactions:
            for item in transaction.transaction_items.all():
                product = item.product
                
                # Use product_id or id as the key
                product_key = product.product_id or str(product.id)
                
                if product_key not in product_sales:
                    product_sales[product_key] = {
                        'product': product.model_name or 'Unknown Product',
                        'reference_number': product_key,
                        'brand': product.category.name if product.category else 'Uncategorized',
                        'total_quantity_sold': 0,
                        'total_turn_over': Decimal('0'),
                        'buying_price': item.purchase_price or Decimal('0'),
                        'sold_price': item.sale_price or Decimal('0'),
                    }
                
                # Update aggregated values
                product_sales[product_key]['total_quantity_sold'] += item.quantity
                product_sales[product_key]['total_turn_over'] += (item.sale_price or Decimal('0')) * item.quantity
                
                # For products with multiple transactions, we'll take the latest buying/sold price
                product_sales[product_key]['buying_price'] = item.purchase_price or product_sales[product_key]['buying_price']
                product_sales[product_key]['sold_price'] = item.sale_price or product_sales[product_key]['sold_price']
        
        # Convert the dictionary to a list and calculate remaining quantity and profit margin
        best_selling = []
        for product_key, data in product_sales.items():
            # Get the product to check remaining quantity
            try:
                product = Product.objects.get(
                    owner=user,
                    product_id=product_key if product_key != 'Unknown ID' else None
                )
                remaining_quantity = product.quantity
            except Product.DoesNotExist:
                remaining_quantity = 0
            
            # Calculate profit margin
            buying_price = data['buying_price']
            sold_price = data['sold_price']
            increase_by = 0
            if buying_price and buying_price > 0 and sold_price:
                increase_by = ((sold_price - buying_price) / buying_price) * 100
                increase_by = round(increase_by, 1)
            
            best_selling.append({
                'product': data['product'],
                'reference_number': data['reference_number'],
                'brand': data['brand'],
                'remaining_quantity': remaining_quantity,
                'turn_over': float(data['total_turn_over']),
                'increase_by': increase_by,
            })
        
        # Sort by turn_over in descending order (you can change to increase_by if preferred)
        best_selling.sort(key=lambda x: x['turn_over'], reverse=True)
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(best_selling, request)
        
        if page is not None:
            return paginator.get_paginated_response(page)
        
        return Response(best_selling[:20] if best_selling else [])


class ExpenseReportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request):
        user = request.user

        all_products = Product.objects.filter(owner=user)
        product_expenses = []
        unique_products = all_products.values('model_name').distinct()

        for product_item in unique_products:
            model_name = product_item['model_name']
            if not model_name:
                continue

            product_data = all_products.filter(model_name=model_name)

            first_product = product_data.first()
            if not first_product:
                continue

            repairs_cost = product_data.aggregate(
                total=Coalesce(Sum('repair_cost'), 0, output_field=DecimalField())
            )['total'] or 0

            shipping_cost = product_data.aggregate(
                total=Coalesce(Sum('shipping_price'), 0, output_field=DecimalField())
            )['total'] or 0

            purchase_cost = product_data.aggregate(
                total=Coalesce(Sum('buying_price'), 0, output_field=DecimalField())
            )['total'] or 0
            total_cost = purchase_cost + repairs_cost + shipping_cost

            impact = ((repairs_cost + shipping_cost) / total_cost) * 100 if total_cost > 0 else 0
            brand = getattr(getattr(first_product, 'category', None), 'name', None)
            quantity = first_product.quantity

            product_expenses.append({
                'model': model_name,
                'reference_number': first_product.product_id,
                'brand': brand,
                'quantity': quantity,
                'purchase_price': float(purchase_cost),
                'repairs': float(repairs_cost),
                'shipping': float(shipping_cost),
                'impact': round(impact, 1),
                'total_cost': float(total_cost),
            })

        product_expenses.sort(key=lambda x: x['impact'], reverse=True)
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(product_expenses, request)
        
        if page is not None:
            return paginator.get_paginated_response(page)
        
        return Response(product_expenses[:20] if product_expenses else [])


class MarketComparisonAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Compare prices with market prices (MSRP)
        """
        user = request.user
        
        # Compare sold prices to MSRP
        market_comparison = Product.objects.filter(
            owner=user,
            availability='sold',
            msrp__isnull=False
        ).annotate(
            difference=F('sold_price') - F('msrp'),
            difference_percent=Case(
                When(msrp__gt=0, then=100 * (F('sold_price') - F('msrp')) / F('msrp')),
                default=Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).values(
            'model_name',
            'msrp',
            'sold_price',
            'difference',
            'difference_percent'
        ).order_by('-difference_percent')
        
        # Format the response to match UI
        formatted_data = []
        
        for item in market_comparison:
            formatted_data.append({
                'product': item['model_name'],
                'msrp_price': float(item['msrp']),
                'sold_price': float(item['sold_price']),
                'difference': float(item['difference']),
                'percentage': f"{round(item['difference_percent'], 1)}%"
            })
        
        return Response(formatted_data)

class ExtractDay(Func):
    function = 'EXTRACT'
    template = '%(function)s(DAY FROM %(expressions)s)'
    output_field = IntegerField()

class StockAgingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        # Get filter parameters
        brands = request.query_params.getlist('brand')
        model = request.query_params.get('model')
        
        # Base query
        query = Product.objects.filter(
            owner=user,
            availability='in_stock'
        ).select_related('category')
        
        # Apply filters
        if brands:
            brand_query = Q()
            for brand in brands:
                brand_query |= Q(category__name__icontains=brand.strip())
            query = query.filter(brand_query)
        
        if model:
            query = query.filter(model_name__icontains=model)
        
        # Calculate date thresholds
        now = timezone.now()
        days_30_ago = (now - timedelta(days=30)).date()
        days_60_ago = (now - timedelta(days=60)).date()
        days_90_ago = (now - timedelta(days=90)).date()
        
        # Annotate products with age categories and days in stock
        products = query.annotate(
            age_category=Case(
                When(date_purchased__gte=days_30_ago, then=Value('less_than_30')),
                When(date_purchased__gte=days_60_ago, then=Value('30_to_60')),
                When(date_purchased__gte=days_90_ago, then=Value('60_to_90')),
                default=Value('91_plus'),
                output_field=CharField()
            ),
            days_in_stock=ExpressionWrapper(
                ExtractDay(today - F('date_purchased')),
                output_field=IntegerField()
            )
        )
        
        # Group products by brand/model
        stock_groups = {}
        stock_count = 0
        
        for product in products:
            # Create a unique group key based on brand and model
            brand_name = product.category.name if product.category else 'Other'
            group_key = f"{brand_name}-{product.model_name}"
            
            if group_key not in stock_groups:
                stock_count += 1
                # Enhanced stock reference with brand abbreviation
                brand_abbr = self.get_brand_abbreviation(brand_name)
                stock_ref = f"{brand_abbr}-{stock_count:03d}"
                
                stock_groups[group_key] = {
                    'stock_ref': stock_ref,
                    'brand': brand_name,
                    'model_name': product.model_name,
                    'less_than_30': 0,
                    '30_to_60': 0,
                    '60_to_90': 0,
                    '91_plus': 0,
                    'total': 0,
                    'days_in_stock': 0,
                    'group_key': group_key  # Added for detail API reference
                }
            
            # Update counts based on age category
            quantity = product.quantity if product.quantity else 1
            stock_groups[group_key][product.age_category] += quantity
            stock_groups[group_key]['total'] += quantity
            
            # Update days in stock
            if product.days_in_stock and product.days_in_stock > stock_groups[group_key]['days_in_stock']:
                stock_groups[group_key]['days_in_stock'] = product.days_in_stock
        
        # Convert to list and sort by days in stock (descending)
        stock_aging_data = sorted(
            stock_groups.values(),
            key=lambda x: x['days_in_stock'],
            reverse=True
        )[:9]
        
        # Calculate totals
        total_less_than_30 = sum(group['less_than_30'] for group in stock_aging_data)
        total_30_to_60 = sum(group['30_to_60'] for group in stock_aging_data)
        total_60_to_90 = sum(group['60_to_90'] for group in stock_aging_data)
        total_91_plus = sum(group['91_plus'] for group in stock_aging_data)
        
        # Prepare chart data
        chart_data = []
        for item in stock_aging_data:
            chart_item = {
                'id': item['stock_ref'],
                'brand': item['brand'],
                'model': item['model_name'],
                'less_than_30': item['less_than_30'],
                '30_to_60': item['30_to_60'],
                '60_to_90': item['60_to_90'],
                '91_plus': item['91_plus'],
                'total': item['total'],
                'days_in_stock': item['days_in_stock'],
                'group_key': item['group_key']  # For detail API reference
            }
            chart_data.append(chart_item)
        
        # Get available filters
        available_brands = Product.objects.filter(
            owner=user,
            availability='in_stock'
        ).exclude(category__isnull=True).values_list(
            'category__name', flat=True
        ).distinct()
        
        available_models = Product.objects.filter(
            owner=user,
            availability='in_stock'
        ).exclude(model_name__isnull=True).values_list(
            'model_name', flat=True
        ).distinct()
        
        return Response({
            'chart_data': chart_data,
            'available_brands': list(filter(None, available_brands)),
            'available_models': list(filter(None, available_models)),
            'summary': {
                'less_than_30_days': total_less_than_30,
                '30_to_60_days': total_30_to_60,
                '60_to_90_days': total_60_to_90,
                '91_plus_days': total_91_plus,
                'total': sum(group['total'] for group in stock_aging_data)
            }
        })
    
    def get_brand_abbreviation(self, brand_name):
        """Generate brand abbreviation for stock reference"""
        if not brand_name or brand_name == 'Other':
            return 'OTH'
        
        # Common watch brand abbreviations
        abbreviations = {
            'rolex': 'RLX',
            'patek philippe': 'PP',
            'audemars piguet': 'AP',
            'omega': 'OMG',
            'cartier': 'CAR',
            'breitling': 'BRT',
            'tag heuer': 'TAG',
            'iwc': 'IWC',
            'jaeger-lecoultre': 'JLC',
            'vacheron constantin': 'VC',
            'panerai': 'PAN',
            'hublot': 'HUB',
            'tudor': 'TUD',
            'seiko': 'SEI',
            'citizen': 'CIT',
            'casio': 'CAS',
            'tissot': 'TIS',
            'longines': 'LON',
            'hamilton': 'HAM',
            'orient': 'ORI',
            'fossil': 'FOS',
            'timex': 'TMX',
            'garmin': 'GAR',
            'apple watch': 'APW',
            'samsung watch': 'SAW',
            'fitbit': 'FIT',
            'suunto': 'SUU',
            'movado': 'MOV',
            'frederique constant': 'FC',
            'montblanc': 'MNT',
            'zenith': 'ZEN',
            'chopard': 'CHO',
            'bvlgari': 'BVL',
            'richard mille': 'RM',
            'grand seiko': 'GS',
            'bell & ross': 'BR',
            'oris': 'ORS',
            'mido': 'MID',
            'certina': 'CER',
            'rado': 'RAD',
            'swatch': 'SWA',
            'maurice lacroix': 'ML',
            'nomos': 'NOM',
            'junghans': 'JUN',
            'g-shock': 'GSH'
        }
        
        brand_lower = brand_name.lower().strip()
        if brand_lower in abbreviations:
            return abbreviations[brand_lower]
        
        # Generate abbreviation from brand name
        words = brand_name.split()
        if len(words) >= 2:
            return ''.join([word[0].upper() for word in words[:3]])
        else:
            return brand_name[:3].upper()

class MonthlyProfitAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        period = request.query_params.get('period', 'month')  # month or week
        
        today = timezone.now().date()
        
        def get_sales_total(queryset):
            # First try to get from transaction-level sale_price
            transaction_total = queryset.aggregate(
                total=Coalesce(Sum('sale_price'), Decimal('0'))
            )['total']
            
            # Then get from item-level calculations
            items_total = TransactionItem.objects.filter(
                transaction__in=queryset
            ).aggregate(
                total=Coalesce(Sum(F('quantity') * F('sale_price')), Decimal('0'))
            )['total']
            
            # Use transaction total if available, otherwise use items total
            return transaction_total if transaction_total > 0 else items_total
        
        def get_purchases_total(queryset):
            # First try to get from transaction-level purchase_price
            transaction_total = queryset.aggregate(
                total=Coalesce(Sum('purchase_price'), Decimal('0'))
            )['total']
            
            # Then get from item-level calculations
            items_total = TransactionItem.objects.filter(
                transaction__in=queryset
            ).aggregate(
                total=Coalesce(Sum(F('quantity') * F('purchase_price')), Decimal('0'))
            )['total']
            
            return transaction_total if transaction_total > 0 else items_total
        
        if period == 'weekly':
            # Get data for the last 12 weeks
            chart_data = []
            for i in range(12, -1, -1):
                week_start = today - timedelta(weeks=i, days=today.weekday())
                week_end = week_start + timedelta(days=6)
                
                sales_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=week_start,
                    date__lte=week_end
                )
                sales = get_sales_total(sales_transactions)
                
                purchase_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=week_start,
                    date__lte=week_end
                )
                purchases = get_purchases_total(purchase_transactions)
                
                profit = sales - purchases
                
                chart_data.append({
                    'period': f"Week {week_start.isocalendar()[1]}",
                    'profit': float(profit) if profit >= 0 else 0.0,
                    'loss': float(abs(profit)) if profit < 0 else 0.0,
                    'net_profit': float(profit)
                })
            
            current_week_start = today - timedelta(days=today.weekday())
            current_week_end = current_week_start + timedelta(days=6)
            
            current_period_sales = get_sales_total(
                TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=current_week_start,
                    date__lte=current_week_end
                )
            )
            
            current_period_purchases = get_purchases_total(
                TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=current_week_start,
                    date__lte=current_week_end
                )
            )
            
            current_period_profit = current_period_sales - current_period_purchases
            
        else:  # month period - SIMPLIFIED LOGIC
            from dateutil.relativedelta import relativedelta
            chart_data = []
            
            # Get last 7 months (including current month)
            for i in range(6, -1, -1):
                # Calculate month start by going back i months from today
                month_start = (today.replace(day=1) - relativedelta(months=i))
                
                # Get last day of the month
                month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
                
                # Get sales for this month
                sales_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=month_start,
                    date__lte=month_end
                )
                sales = get_sales_total(sales_transactions)
                
                purchase_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=month_start,
                    date__lte=month_end
                )
                purchases = get_purchases_total(purchase_transactions)
                
                profit = sales - purchases
                
                chart_data.append({
                    'period': month_start.strftime('%b %Y'),
                    'profit': float(profit) if profit >= 0 else 0.0,
                    'loss': float(abs(profit)) if profit < 0 else 0.0,
                    'net_profit': float(profit)
                })
            
            # Current month calculation
            month_start = today.replace(day=1)
            
            current_period_sales = get_sales_total(
                TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=month_start,
                    date__lte=today
                )
            )
            
            current_period_purchases = get_purchases_total(
                TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=month_start,
                    date__lte=today
                )
            )
            
            current_period_profit = current_period_sales - current_period_purchases
        
        total_net_profit = sum(period['net_profit'] for period in chart_data)
        total_profit = sum(period['profit'] for period in chart_data)
        total_loss = sum(period['loss'] for period in chart_data)
        
        return Response({
            'summary': {
                'profit': {
                    'total': total_profit,
                    'net_total': total_net_profit,
                    'periods': [period['period'] for period in chart_data]
                },
                'loss': {
                    'total': total_loss,
                    'view_type': period
                },
                'net_profit': total_net_profit
            },
            'chart_data': chart_data,
            'current_period': {
                'period': today.strftime('%b %Y') if period == 'month' else f"Week {today.isocalendar()[1]}",
                'date': today.strftime('%b %Y') if period == 'month' else f"Week {today.isocalendar()[1]}",
                'value': f"{current_period_profit:,.0f}",
                'sales': f"{current_period_sales:,.0f}",
                'purchases': f"{current_period_purchases:,.0f}"
            }
        })
class UserSpecificReportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get user specific performance data
        """
        user = request.user
        
        # Calculate user specific metrics
        total_products = Product.objects.filter(owner=user).count()
        total_sold = Product.objects.filter(owner=user, availability='sold').count()
        
        # Calculate average profit margin
        avg_profit_margin = Product.objects.filter(
            owner=user,
            availability='sold',
            profit__isnull=False,
            buying_price__gt=0
        ).annotate(
            profit_margin_calc=(F('profit') * 100.0 / F('buying_price'))
        ).aggregate(
            avg_margin=Avg('profit_margin_calc', output_field=DecimalField())
        )['avg_margin'] or 0
        
        # Calculate average days to sell
        avg_days_to_sell = Product.objects.filter(
            owner=user,
            availability='sold',
            date_purchased__isnull=False,
            date_sold__isnull=False
        ).annotate(
            days_to_sell=Cast(F('date_sold') - F('date_purchased'), output_field=IntegerField())
        ).aggregate(
            avg_days=Avg('days_to_sell', output_field=FloatField())
        )['avg_days'] or 0
        
        if isinstance(avg_days_to_sell, timedelta):
            avg_days_to_sell = avg_days_to_sell.days
        
        # Calculate sell-through rate
        sell_through_rate = 0
        if total_products > 0:
            sell_through_rate = (total_sold / total_products) * 100
        
        return Response({
            'total_products': total_products,
            'total_sold': total_sold,
            'sell_through_rate': float(sell_through_rate),
            'avg_profit_margin': float(avg_profit_margin),
            'avg_days_to_sell': float(avg_days_to_sell)
        })


class StockTurnoverAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get stock turnover analysis
        """
        user = request.user
        
        # Calculate inventory turnover by category
        categories = Category.objects.all()
        turnover_data = []
        
        for category in categories:
            sold_products = Product.objects.filter(
                owner=user,
                category=category,
                availability='sold'
            )
            
            current_inventory = Product.objects.filter(
                owner=user,
                category=category,
                availability='in_stock'
            )
            
            sold_value = sold_products.aggregate(
                total=Coalesce(Sum('sold_price'), 0, output_field=DecimalField())
            )['total'] or 0
            
            inventory_value = current_inventory.aggregate(
                total=Coalesce(Sum('buying_price'), 0, output_field=DecimalField())
            )['total'] or 0
            
            # Calculate turnover ratio
            turnover_ratio = 0
            if inventory_value > 0:
                turnover_ratio = float(sold_value) / float(inventory_value)
            
            turnover_data.append({
                'category': category.name,
                'sold_value': float(sold_value),
                'inventory_value': float(inventory_value),
                'turnover_ratio': float(turnover_ratio)
            })
        
        # Sort by turnover ratio
        turnover_data.sort(key=lambda x: x['turnover_ratio'], reverse=True)
        
        return Response(turnover_data)


class LiveInventoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get live inventory data
        """
        user = request.user
        
        # Get inventory summary
        total_items = Product.objects.filter(owner=user, availability='in_stock').count()
        total_value = Product.objects.filter(owner=user, availability='in_stock').aggregate(
            total=Coalesce(Sum('buying_price'), 0, output_field=DecimalField())
        )['total'] or 0
        
        # Get category breakdown
        categories = Product.objects.filter(
            owner=user, 
            availability='in_stock'
        ).values('category__name').annotate(
            count=Count('id'),
            value=Coalesce(Sum('buying_price'), 0, output_field=DecimalField())
        ).order_by('-value')
        
        formatted_categories = []
        for category in categories:
            formatted_categories.append({
                'category': category['category__name'] or 'Uncategorized',
                'count': category['count'],
                'value': float(category['value'])
            })
        
        return Response({
            'total_items': total_items,
            'total_value': float(total_value),
            'categories': formatted_categories
        })


class PurchaseSalesReportAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get purchase and sales report with period filtering (month/week)
        """
        user = request.user
        period = request.query_params.get('period', 'monthly')  # month or week
        
        today = timezone.now().date()
        
        def get_sales_total(queryset):

            transaction_total = queryset.aggregate(
                total=Coalesce(Sum('sale_price'), Decimal('0'))
            )['total']
            
            items_total = TransactionItem.objects.filter(
                transaction__in=queryset
            ).aggregate(
                total=Coalesce(Sum(F('quantity') * F('sale_price')), Decimal('0'))
            )['total']
            
            return max(transaction_total, items_total)
        
        def get_purchases_total(queryset):
            transaction_total = queryset.aggregate(
                total=Coalesce(Sum('purchase_price'), Decimal('0'))
            )['total']
            
            items_total = TransactionItem.objects.filter(
                transaction__in=queryset
            ).aggregate(
                total=Coalesce(Sum(F('quantity') * F('purchase_price')), Decimal('0'))
            )['total']
            
            return max(transaction_total, items_total)
        
        if period == 'weekly':
            # Get data for the last 12 weeks
            start_date = today - timedelta(weeks=12)
            
            chart_data = []
            for i in range(12, -1, -1):
                week_start = today - timedelta(weeks=i)
                week_end = week_start + timedelta(days=6)
                
                sales_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=week_start,
                    date__lte=week_end
                )
                sales = get_sales_total(sales_transactions)
                
                # Get purchases
                purchase_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=week_start,
                    date__lte=week_end
                )
                purchases = get_purchases_total(purchase_transactions)
                
                chart_data.append({
                    'period': f"Week {week_start.isocalendar()[1]}",  # Week number
                    'date': f"Week {week_start.isocalendar()[1]}",  # Week number
                    'purchases': float(purchases),
                    'sales': float(sales)
                })
            
            current_period_sales = get_sales_total(
                TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__week=today.isocalendar()[1],
                    date__year=today.year
                )
            )
            
        else: 
            chart_data = []
            for i in range(6, -1, -1):
                month = today.month - i
                year = today.year
                while month < 1:
                    month += 12
                    year -= 1
                
                month_start = date(year, month, 1)
                if month == 12:
                    month_end = date(year+1, 1, 1)
                else:
                    month_end = date(year, month+1, 1)
                
                sales_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=month_start,
                    date__lt=month_end
                )
                sales = get_sales_total(sales_transactions)
                
                purchase_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=month_start,
                    date__lt=month_end
                )
                purchases = get_purchases_total(purchase_transactions)
                
                chart_data.append({
                    'period': month_start.strftime('%b'),  # Month abbreviation
                    'purchases': float(purchases),
                    'sales': float(sales)
                })
            
            current_period_sales = get_sales_total(
                TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__month=today.month,
                    date__year=today.year
                )
            )
        
        total_purchases = sum(period['purchases'] for period in chart_data)
        total_sales = sum(period['sales'] for period in chart_data)
        
        return Response({
            'summary': {
                'purchases': {
                    'total': total_purchases,
                    'periods': [period['period'] for period in chart_data]
                },
                'sales': {
                    'total': total_sales,
                    'view_type': period
                }
            },
            'chart_data': chart_data,
            'current_period': {
                'period': today.strftime('%b') if period == 'monthly' else f"Week {today.isocalendar()[1]}",
                'value': format(current_period_sales, ',.0f')
            }
        })
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        view_type = request.query_params.get('view', 'month')  # month or week
        
        today = timezone.now().date()
        current_month = today.month
        current_year = today.year
        
        def get_sales_total(queryset):
            return queryset.aggregate(
                total=Coalesce(Sum('sale_price'), Decimal('0'))
            )['total']
        
        def get_purchases_total(queryset):
            return queryset.aggregate(
                total=Coalesce(Sum('purchase_price'), Decimal('0'))
            )['total']
        
        # Determine if we're showing weekly or monthly data
        is_weekly = request.query_params.get('period', '').lower() == 'weekly'
        
        # Calculate totals for the current period from transactions
        if not is_weekly:
            # Monthly data
            current_period_transactions = TransactionHistory.objects.filter(
                user=user,
                transaction_type='sale',
                date__month=current_month,
                date__year=current_year
            )
            current_period_sales = get_sales_total(current_period_transactions)
        else:
            # Weekly data
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            current_period_transactions = TransactionHistory.objects.filter(
                user=user,
                transaction_type='sale',
                date__gte=start_of_week,
                date__lte=end_of_week
            )
            current_period_sales = get_sales_total(current_period_transactions)
        
        periods_data = []
        
        if not is_weekly:
            # Monthly data (6 months back)
            for i in range(6, -1, -1): 
                month = today.month - i
                year = today.year
                while month < 1:
                    month += 12
                    year -= 1
                
                month_start = date(year, month, 1)
                if month == 12:
                    month_end = date(year+1, 1, 1)
                else:
                    month_end = date(year, month+1, 1)
                
                sales_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=month_start,
                    date__lt=month_end
                )
                sales = get_sales_total(sales_transactions)
                
                purchase_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=month_start,
                    date__lt=month_end
                )
                purchases = get_purchases_total(purchase_transactions)
                
                periods_data.append({
                    'period': month_start.strftime('%b'),  # Short month name
                    'date': month_start.strftime('%b'),
                    'purchase': float(purchases),
                    'sale': float(sales)
                })
        else:
            # Weekly data (6 weeks back)
            current_week_number = today.isocalendar()[1]  # Get current week number
            for i in range(6, -1, -1):
                week_number = current_week_number - i
                year = today.year
                
                # Handle year transition for week numbers
                if week_number < 1:
                    week_number += 52
                    year -= 1
                
                start_date = date.fromisocalendar(year, week_number, 1)
                end_date = date.fromisocalendar(year, week_number, 7)
                
                sales_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='sale',
                    date__gte=start_date,
                    date__lte=end_date
                )
                sales = get_sales_total(sales_transactions)
                
                purchase_transactions = TransactionHistory.objects.filter(
                    user=user,
                    transaction_type='purchase',
                    date__gte=start_date,
                    date__lte=end_date
                )
                purchases = get_purchases_total(purchase_transactions)
                
                periods_data.append({
                    'period': f"Week {week_number}",
                    'date': f"Week {week_number}",
                    'purchase': float(purchases),
                    'sale': float(sales)
                })
        
        total_purchases = sum(m['purchase'] for m in periods_data)
        total_sales = sum(m['sale'] for m in periods_data)
        
        response_data = {
            'summary': {
                'purchases': {
                    'total': total_purchases,
                    'periods': [m['period'] for m in periods_data]
                },
                'sales': {
                    'total': total_sales,
                    'view_type': 'weekly' if is_weekly else 'month'
                }
            },
            'chart_data': periods_data,
            'current_period': {
                'period': today.strftime('%b') if not is_weekly else f"Week {current_week_number}",
                'value': format(current_period_sales, ',.0f')
            }
        }
        
        return Response(response_data)
    

class StockDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination
    
    def get(self, request, stock_ref):
        user = request.user
        today = timezone.now().date()
        
        try:
            products = Product.objects.filter(
                owner=user,
                availability='in_stock'
            ).select_related('category').annotate(
                age_category=Case(
                    When(date_purchased__gte=(timezone.now() - timedelta(days=30)).date(), 
                         then=Value('less_than_30')),
                    When(date_purchased__gte=(timezone.now() - timedelta(days=60)).date(), 
                         then=Value('30_to_60')),
                    When(date_purchased__gte=(timezone.now() - timedelta(days=90)).date(), 
                         then=Value('60_to_90')),
                    default=Value('91_plus'),
                    output_field=CharField()
                ),
                days_in_stock=ExpressionWrapper(
                    ExtractDay(today - F('date_purchased')),
                    output_field=IntegerField()
                )
            )
            
            target_group = None
            stock_groups = {}
            stock_count = 0
            
            for product in products:
                brand_name = product.category.name if product.category else 'Other'
                group_key = f"{brand_name}-{product.model_name}"
                
                if group_key not in stock_groups:
                    stock_count += 1
                    brand_abbr = self.get_brand_abbreviation(brand_name)
                    generated_ref = f"{brand_abbr}-{stock_count:03d}"
                    
                    if generated_ref == stock_ref:
                        target_group = {
                            'brand': brand_name,
                            'model_name': product.model_name,
                            'group_key': group_key
                        }
                        break
                    
                    stock_groups[group_key] = generated_ref
            
            if not target_group:
                return Response(
                    {'error': 'Stock reference not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            detailed_products = Product.objects.filter(
                owner=user,
                availability='in_stock',
                category__name=target_group['brand'],
                model_name=target_group['model_name']
            ).select_related('category').annotate(
                age_category=Case(
                    When(date_purchased__gte=(timezone.now() - timedelta(days=30)).date(), 
                         then=Value('less_than_30')),
                    When(date_purchased__gte=(timezone.now() - timedelta(days=60)).date(), 
                         then=Value('30_to_60')),
                    When(date_purchased__gte=(timezone.now() - timedelta(days=90)).date(), 
                         then=Value('60_to_90')),
                    default=Value('91_plus'),
                    output_field=CharField()
                ),
                days_in_stock=ExpressionWrapper(
                    ExtractDay(today - F('date_purchased')),
                    output_field=IntegerField()
                )
            ).order_by('-date_purchased')
            
            # Calculate age summary for ALL products (before pagination)
            age_summary = {
                'less_than_30': 0,
                '30_to_60': 0,
                '60_to_90': 0,
                '91_plus': 0
            }
            
            total_items = detailed_products.count()
            oldest_stock_days = 0
            
            for product in detailed_products:
                quantity = product.quantity if product.quantity else 1
                age_summary[product.age_category] += quantity
                if product.days_in_stock > oldest_stock_days:
                    oldest_stock_days = product.days_in_stock
            
            paginator = self.pagination_class()
            paginated_products = paginator.paginate_queryset(detailed_products, request)
            
            product_details = []
            for product in paginated_products:
                quantity = product.quantity if product.quantity else 1
                
                product_details.append({
                    'id': product.id,
                    'brand': product.category.name,
                    'model_name': product.model_name,
                    'reference_number': product.product_id,
                    'quantity': quantity,
                    'serial_number': getattr(product, 'serial_number', ''),
                    'date_purchased': product.date_purchased,
                    'days_in_stock': product.days_in_stock,
                    'age_category': product.age_category,
                    'purchase_price': getattr(product, 'purchase_price', None),
                    'selling_price': getattr(product, 'selling_price', None),
                    'condition': getattr(product, 'condition', ''),
                    'storage_location': getattr(product, 'storage_location', ''),
                    'notes': getattr(product, 'notes', '')
                })
            
            # Build response data
            response_data = {
                'stock_ref': stock_ref,
                'brand': target_group['brand'],
                'model_name': target_group['model_name'],
                'total_items': total_items,
                'age_summary': age_summary,
                'products': product_details,
                'oldest_stock_days': oldest_stock_days
            }
            
            # Return paginated response
            return paginator.get_paginated_response(response_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving stock details: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_brand_abbreviation(self, brand_name):
        """Generate brand abbreviation for stock reference (same as main API)"""
        if not brand_name or brand_name == 'Other':
            return 'OTH'
        
        # Common watch brand abbreviations
        abbreviations = {
            'rolex': 'RLX',
            'patek philippe': 'PP',
            'audemars piguet': 'AP',
            'omega': 'OMG',
            'cartier': 'CAR',
            'breitling': 'BRT',
            'tag heuer': 'TAG',
            'iwc': 'IWC',
            'jaeger-lecoultre': 'JLC',
            'vacheron constantin': 'VC',
            'panerai': 'PAN',
            'hublot': 'HUB',
            'tudor': 'TUD',
            'seiko': 'SEI',
            'citizen': 'CIT',
            'casio': 'CAS',
            'tissot': 'TIS',
            'longines': 'LON',
            'hamilton': 'HAM',
            'orient': 'ORI',
            'fossil': 'FOS',
            'timex': 'TMX',
            'garmin': 'GAR',
            'apple watch': 'APW',
            'samsung watch': 'SAW',
            'fitbit': 'FIT',
            'suunto': 'SUU',
            'movado': 'MOV',
            'frederique constant': 'FC',
            'montblanc': 'MNT',
            'zenith': 'ZEN',
            'chopard': 'CHO',
            'bvlgari': 'BVL',
            'richard mille': 'RM',
            'grand seiko': 'GS',
            'bell & ross': 'BR',
            'oris': 'ORS',
            'mido': 'MID',
            'certina': 'CER',
            'rado': 'RAD',
            'swatch': 'SWA',
            'maurice lacroix': 'ML',
            'nomos': 'NOM',
            'junghans': 'JUN',
            'g-shock': 'GSH'
        }
        
        brand_lower = brand_name.lower().strip()
        if brand_lower in abbreviations:
            return abbreviations[brand_lower]
        
        words = brand_name.split()
        if len(words) >= 2:
            return ''.join([word[0].upper() for word in words[:3]])
        else:
            return brand_name[:3].upper()