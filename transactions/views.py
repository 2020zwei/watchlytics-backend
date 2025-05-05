from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .models import TransactionHistory
from .serializers import TransactionHistorySerializer, TransactionCreateSerializer
from inventory.models import Product
from customers.models import Customer


class TransactionHistoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'sale_category', 'date', 'product', 'customer']
    search_fields = ['notes', 'product__name', 'customer__name']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        # Users should only see their own transactions
        return TransactionHistory.objects.filter(user=self.request.user)

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
        sales_amount = sum(transaction.amount for transaction in queryset.filter(transaction_type='sale'))
        purchases_amount = sum(transaction.amount for transaction in queryset.filter(transaction_type='purchase'))
        
        # Calculate total profit
        total_profit = sum(transaction.profit for transaction in queryset.filter(transaction_type='sale'))
        
        return Response({
            'total_sales': total_sales,
            'total_purchases': total_purchases,
            'sales_amount': sales_amount,
            'purchases_amount': purchases_amount,
            'total_profit': total_profit
        })