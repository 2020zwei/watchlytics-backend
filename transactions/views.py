from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .models import TransactionHistory, TransactionItem
from .serializers import TransactionHistorySerializer, TransactionCreateSerializer
from inventory.models import Product
from customers.models import Customer


class TransactionHistoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'sale_category', 'date', 'transaction_items__product', 'customer', 'name_of_trade']
    search_fields = ['name_of_trade', 'notes', 'transaction_items__product__name', 'customer__name']
    ordering_fields = ['date', 'purchase_price', 'sale_price', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        # Users should only see their own transactions
        return TransactionHistory.objects.filter(user=self.request.user).prefetch_related('transaction_items', 'transaction_items__product')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TransactionCreateSerializer
        return TransactionHistorySerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get transaction summary statistics
        """
        queryset = self.get_queryset()
        
        # Calculate total sales and purchases
        total_sales = queryset.filter(transaction_type='sale').count()
        total_purchases = queryset.filter(transaction_type='purchase').count()
        
        # Calculate total sales amount and purchases amount
        sales_transactions = queryset.filter(transaction_type='sale')
        purchases_transactions = queryset.filter(transaction_type='purchase')
        
        sales_amount = sum(transaction.total_sale_price or 0 for transaction in sales_transactions)
        purchases_amount = sum(transaction.total_purchase_price or 0 for transaction in purchases_transactions)
        
        # Calculate total profit
        total_profit = sum(transaction.profit or 0 for transaction in sales_transactions)
        
        product_stats = {}
        for item in TransactionItem.objects.filter(transaction__user=request.user):
            product_id = item.product_id
            if product_id not in product_stats:
                product_stats[product_id] = {
                    'name': item.product.name,
                    'total_sold': 0,
                    'total_purchased': 0,
                    'revenue': 0,
                    'cost': 0
                }
            
            if item.transaction.transaction_type == 'sale':
                product_stats[product_id]['total_sold'] += item.quantity
                product_stats[product_id]['revenue'] += item.quantity * item.unit_price
            else:
                product_stats[product_id]['total_purchased'] += item.quantity
                product_stats[product_id]['cost'] += item.quantity * item.unit_price
        
        return Response({
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'sales_amount': sales_amount,
            'purchases_amount': purchases_amount,
            'total_profit': total_profit,
            'product_stats': product_stats
        })


class TransactionItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return TransactionItem.objects.filter(transaction__user=self.request.user)