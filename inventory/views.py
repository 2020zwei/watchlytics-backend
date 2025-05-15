from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer, ProductCreateSerializer
from rest_framework.permissions import AllowAny
from io import TextIOWrapper
from inventory.models import Product, Category
from transactions.models import TransactionHistory
from datetime import timedelta
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q, F
from .pagination import CustomPagination
import csv
import openpyxl
from .models import Product, User, Category
from django.utils.dateparse import parse_date
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.db import transaction
from transactions.models import TransactionHistory, TransactionItem

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination
    
    def get_queryset(self):
        user = self.request.user
        queryset = Product.objects.filter(owner=user)
        
        brands = self.request.query_params.getlist('brand')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        condition = self.request.query_params.get('condition')
        buyer = self.request.query_params.get('buyer')
        seller = self.request.query_params.get('seller')
        sort_by = self.request.query_params.get('sort_by', 'created_at')  # Default sort by created_at
        sort_direction = self.request.query_params.get('sort_direction', 'desc')  # Default descending
        
        if brands:
            brand_queries = []
            for brand in brands:
                brand_words = brand.strip().split()
                if brand_words:
                    product_filters = []
                    for word in brand_words:
                        word_filter = Q(model_name__icontains=word) | Q(category__name__icontains=word)
                        product_filters.append(word_filter)
                    
                    if product_filters:
                        combined_filter = product_filters[0]
                        for filter_item in product_filters[1:]:
                            combined_filter &= filter_item
                        brand_queries.append(combined_filter)
            
            if brand_queries:
                brand_filter = brand_queries[0]
                for query in brand_queries[1:]:
                    brand_filter |= query
                queryset = queryset.filter(brand_filter)
        
        if start_date:
            queryset = queryset.filter(date_purchased__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(date_purchased__lte=end_date)
        
        if condition:
            queryset = queryset.filter(condition=condition)
        
        if buyer:
            queryset = queryset.filter(sold_source__icontains=buyer)
        
        if seller:
            queryset = queryset.filter(purchased_from__icontains=seller)
        
        valid_sort_fields = ['id', 'created_at']
        if sort_by in valid_sort_fields:
            if sort_direction.lower() == 'desc':
                queryset = queryset.order_by(f'-{sort_by}')
            else:
                queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProductCreateSerializer
        return ProductSerializer
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def create_product(self, request):
        serializer = ProductCreateSerializer(data=request.data, files=request.FILES)
        if serializer.is_valid():
            product = serializer.save(owner=request.user)
            response_serializer = ProductSerializer(product)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def unsold(self, request):
        unsold_products = self.get_queryset().filter(date_sold__isnull=True)
        serializer = self.get_serializer(unsold_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def sold(self, request):
        sold_products = self.get_queryset().filter(date_sold__isnull=False)
        serializer = self.get_serializer(sold_products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def mark_as_sold(self, request, pk=None):
        product = self.get_object()
        sold_data = {
            'date_sold': request.data.get('date_sold', timezone.now().date()),
            'sold_price': request.data.get('sold_price'),
            'sold_source': request.data.get('sold_source'),
            'status': 'sold'
        }
        
        serializer = self.get_serializer(product, data=sold_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    @action(detail=True, methods=['put', 'patch'])
    def update_product(self, request, pk=None):
        try:
            product = self.get_object()
            
            # Choose appropriate serializer based on update type
            if request.method == 'PUT':
                serializer = ProductSerializer(product, data=request.data)
            else:
                serializer = ProductSerializer(product, data=request.data, partial=True)
            
            if serializer.is_valid():
                if 'buying_price' in request.data and float(request.data['buying_price']) <= 0:
                    return Response(
                        {"buying_price": "Buying price must be greater than 0"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if request.data.get('status') == 'sold' and not request.data.get('sold_price'):
                    return Response(
                        {"sold_price": "Sold price is required when marking a product as sold"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                updated_product = serializer.save()
                response_serializer = ProductSerializer(updated_product)
                return Response(response_serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
        except Exception as e:
            return Response(
                {"error": f"Failed to update product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_product(self, request, pk=None):
        try:
            product = self.get_object()
            
            # if product.orders.exists():
            #     return Response(
            #         {"error": "Cannot delete product that is referenced by orders"},
            #         status=status.HTTP_400_BAD_REQUEST
            #     )
            
            # Standard deletion
            model_name = product.model_name
            product.delete()
            
            return Response(
                {"message": f"Product '{model_name}' successfully deleted"},
                status=status.HTTP_204_NO_CONTENT
            )
        
        except Exception as e:
            return Response(
                {"error": f"Failed to delete product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=7)
        
        categories_count = Category.objects.filter(
            products__owner=user,
            products__created_at__gte=seven_days_ago
        ).distinct().count()

        total_products = Product.objects.filter(
            owner=user,
            created_at__gte=seven_days_ago
        ).count()
        
        sales_transactions = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale',
            date__gte=seven_days_ago
        )
        
        revenue = sum(transaction.total_sale_price for transaction in sales_transactions)
        
        transaction_items = TransactionItem.objects.filter(
            transaction__user=user,
            transaction__transaction_type='sale',
            transaction__date__gte=seven_days_ago
        )
        
        top_selling_count = transaction_items.count()
        top_selling_cost = sum(item.total_purchase_price for item in transaction_items)
        
        ordered_count = Product.objects.filter(
            owner=user,
            availability='reserved'
        ).count()
        
        not_in_stock = Product.objects.filter(
            owner=user,
            quantity=0,
            availability='in_stock'
        ).count()
        
        profit = sum(transaction.profit or 0 for transaction in sales_transactions)
        
        return Response({
            "categories": {
                "count": categories_count,
                "label": "Last 7 days"
            },
            "total_products": {
                "count": total_products,
                "label": "Last 7 days",
                "revenue": float(revenue)
            },
            "top_selling": {
                "count": top_selling_count,
                "label": "Last 7 days",
                "cost": float(top_selling_cost)
            },
            "low_stocks": {
                "ordered": ordered_count,
                "not_in_stock": not_in_stock
            },
            "profit": {
                "amount": float(profit),
                "label": "Last 7 days"
            }
        })
    

class ProductCSVUploadAPIView(APIView):

    @staticmethod
    def parse_decimal(value, default=0):
        if value is None:
            return Decimal(default)
        try:
            if isinstance(value, str):
                value = value.strip().replace(',', '')
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def to_date(value):
        if not value:
            return None
            
        if isinstance(value, datetime):
            return value.date()
            
        if not isinstance(value, str):
            return None
            
        value = value.strip()
        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y']
        
        for date_format in formats:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
                
        return None
            
    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get('excel_file')
        if not uploaded_file:
            return Response({'error': 'No file provided.'}, status=400)

        filename = uploaded_file.name.lower()

        try:
            # Parse file based on extension
            if filename.endswith('.csv'):
                reader = csv.DictReader(TextIOWrapper(uploaded_file.file, encoding='utf-8'))
                rows = list(reader)
            elif filename.endswith(('.xlsx', '.xls')):
                wb = openpyxl.load_workbook(uploaded_file)
                sheet = wb.active
                headers = [cell.value for cell in sheet[1] if cell.value]
                rows = [
                    {headers[i]: cell.value for i, cell in enumerate(row) if i < len(headers)}
                    for row in sheet.iter_rows(min_row=2)
                ]
            else:
                return Response({'error': 'Unsupported file format. Please upload CSV or Excel file.'}, status=400)
        except Exception as e:
            return Response({'error': f'Error processing file: {str(e)}'}, status=400)

        created = 0
        updated = 0
        errors = []
        user = self.request.user
        
        with transaction.atomic():
            for index, row in enumerate(rows, start=2):
                try:
                    normalized_row = self._normalize_row(row)
                    
                    product_id = normalized_row.get('Reference')
                    serial_number = normalized_row.get('Serial Number')
                    model_name = normalized_row.get('Model Name')
                    
                    if not (product_id or serial_number or model_name):
                        continue
                        
                    buy_price = self.parse_decimal(normalized_row.get('Buy Price'))
                    total_cost = self.parse_decimal(normalized_row.get('Total Cost'))
                    sell_price = self.parse_decimal(normalized_row.get('Sell Price'))
                    shipping_price = self.parse_decimal(normalized_row.get('Shipping'))
                    repair_cost = self.parse_decimal(normalized_row.get('Expense'))
                    
                    profit = sell_price - buy_price
                    profit_margin = int((profit / buy_price) * 100) if buy_price else 0
                    
                    brand_name = normalized_row.get('Brand') or 'Unnamed Product'
                    category_name = brand_name.strip()
                    category, _ = Category.objects.get_or_create(
                        name__iexact=category_name,
                        defaults={'name': category_name}
                    )
                    
                    date_purchased = self.to_date(normalized_row.get('Purchase Date'))
                    sold_date = self.to_date(normalized_row.get('Sold Date'))
                    
                    if not product_id:
                        product_id = f'custom-id-{index}'

                    existing_product = None
                    if product_id or serial_number:
                        q_filter = Q()
                        if product_id:
                            q_filter |= Q(product_id=product_id)
                        if serial_number:
                            q_filter |= Q(serial_number=serial_number)
                        
                        existing_products = Product.objects.filter(q_filter, owner=user)
                        if existing_products.exists():
                            existing_product = existing_products.first()

                    product_data = {
                        'owner': user,
                        'model_name': model_name or brand_name,
                        'product_id': product_id,
                        'serial_number': serial_number,
                        'category': category,
                        'profit_margin': profit_margin,
                        'availability': self.map_availability(normalized_row.get('Deal Status')),
                        'buying_price': buy_price,
                        'shipping_price': shipping_price,
                        'repair_cost': repair_cost,
                        'sold_price': sell_price,
                        'quantity': normalized_row.get('Quantity') or 1,
                        'date_purchased': date_purchased,
                        'date_sold': sold_date,
                        'source_of_sale': normalized_row.get('Sold To') or '',
                        'purchased_from': normalized_row.get('Bought From') or '',
                        'sold_source': normalized_row.get('Payment Sent account') or '',
                        'listed_on': normalized_row.get('Delivery Content') or '',
                        'wholesale_price': total_cost,
                    }

                    if existing_product:
                        for key, value in product_data.items():
                            setattr(existing_product, key, value)
                        existing_product.save()
                        updated += 1
                    else:
                        Product.objects.create(**product_data)
                        created += 1
                        
                except Exception as e:
                    errors.append({'row': index, 'error': str(e)})

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors,
            'total_processed': created + updated,
            'total_rows': len(rows),
        }, status=201)

    def _normalize_row(self, row):
        return {
            key.strip() if isinstance(key, str) else key: 
            (value.strip() if isinstance(value, str) else value)
            for key, value in row.items()
            if key is not None
        }

    def map_availability(self, deal_status):
        if not deal_status:
            return 'in_stock'
            
        if isinstance(deal_status, str):
            deal_status = deal_status.strip().lower()
            
        mapping = {
            'sold': 'sold',
            'in stock': 'in_stock',
            'instock': 'in_stock',
            'reserved': 'reserved',
            'in repair': 'in_repair',
            'repair': 'in_repair'
        }
        return mapping.get(deal_status.lower(), 'in_stock')