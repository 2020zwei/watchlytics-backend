from django.db.models import Count, Sum, Max, Q, F, Value, BooleanField, DecimalField
from django.db.models.functions import Coalesce
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Customer
from .serializers import CustomerSerializer, CustomerDetailSerializer, CustomerCreateSerializer
from transactions.models import TransactionHistory


class CustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'phone', 'address', 'notes']
    ordering_fields = ['name', 'created_at', 'updated_at', 'orders_count', 'last_purchase_date', 'total_spending']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)
        
        queryset = queryset.annotate(
            orders_count=Count('transactions_customer', distinct=True),
            last_purchase_date=Max('transactions_customer__date'),
            total_spending=Coalesce(
                Sum('transactions_customer__sale_price', 
                    filter=Q(transactions_customer__transaction_type='sale'),
                    output_field=DecimalField()), 
                Value(0, output_field=DecimalField())
            ),
            follow_up=Value(False, output_field=BooleanField())
        )
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter.lower() in ('active', 'true', '1'):
                queryset = queryset.filter(status=True)
            elif status_filter.lower() in ('inactive', 'false', '0'):
                queryset = queryset.filter(status=False)
        
        min_spending = self.request.query_params.get('min_spending')
        max_spending = self.request.query_params.get('max_spending')
        if min_spending:
            queryset = queryset.filter(total_spending__gte=min_spending)
        if max_spending:
            queryset = queryset.filter(total_spending__lte=max_spending)
        
        min_orders = self.request.query_params.get('min_orders')
        max_orders = self.request.query_params.get('max_orders')
        if min_orders:
            queryset = queryset.filter(orders_count__gte=min_orders)
        if max_orders:
            queryset = queryset.filter(orders_count__lte=max_orders)
        
        follow_up = self.request.query_params.get('follow_up')
        if follow_up:
            if follow_up.lower() in ('yes', 'true', '1'):
                queryset = queryset.filter(follow_up=True)
            elif follow_up.lower() in ('no', 'false', '0'):
                queryset = queryset.filter(follow_up=False)
                
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomerDetailSerializer
        elif self.action == 'create':
            return CustomerCreateSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def toggle_status(self, request, pk=None):
        customer = self.get_object()
        customer.status = not customer.status
        customer.save()
        
        serializer = self.get_serializer(customer)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_for_follow_up(self, request, pk=None):
        customer = self.get_object()
        
        serializer = self.get_serializer(customer)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        
        total_customers = queryset.count()
        active_customers = queryset.filter(status=True).count()
        inactive_customers = queryset.filter(status=False).count()
        
        total_spending = queryset.aggregate(
            total=Coalesce(
                Sum('transactions_customer__sale_price', 
                    filter=Q(transactions_customer__transaction_type='sale'),
                    output_field=DecimalField()),
                Value(0, output_field=DecimalField())
            )
        )['total'] or 0
        
        customers_with_transactions = queryset.filter(transactions_customer__isnull=False).distinct().count()
        avg_spending = (total_spending / customers_with_transactions 
                       if customers_with_transactions > 0 
                       else 0)
        
        top_spenders = queryset.order_by('-total_spending')[:5].values('id', 'name', 'total_spending')
        
        data = {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'inactive_customers': inactive_customers,
            'total_spending': total_spending,
            'average_spending': avg_spending,
            'top_spenders': list(top_spenders)
        }
        
        return Response(data)
    
    @action(detail=True, methods=['get'])
    def transaction_history(self, request, pk=None):
        customer = self.get_object()
        transactions = TransactionHistory.objects.filter(customer=customer).order_by('-date')
        
        transaction_data = []
        for tx in transactions:
            transaction_data.append({
                'id': tx.id,
                'date': tx.date,
                'type': tx.transaction_type,
                'amount': tx.sale_price or 0,
                'name': tx.name_of_trade,
                'notes': tx.notes
            })
        
        return Response(transaction_data)
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'message': 'Export functionality placeholder',
            'data': serializer.data
        })