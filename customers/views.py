from django.db.models import Count, Sum, Max, Q, F, Value, BooleanField, DecimalField, Avg, Case, When, CharField
from django.db import models
from rest_framework.views import APIView
from django.db.models.functions import Coalesce
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Customer
from .serializers import CustomerSerializer, CustomerDetailSerializer, CustomerCreateSerializer
from transactions.serializers import TransactionHistorySerializer
from rest_framework import generics
from django.db import transaction
from django.utils import timezone
from .models import Customer, FollowUp, CustomerTag
from transactions.models import TransactionHistory, TransactionItem
from .serializers import DashboardMetricsSerializer, CustomerOrderSerializer, CustomerBulkSerializer, BulkActionSerializer
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
import logging
from django.core.mail import EmailMessage


logger = logging.getLogger(__name__)

class CustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'created_at', 'updated_at', 'orders_count', 'last_purchase_date', 'total_spending']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)
        
        universal_search = self.request.query_params.get('search', None)
        if universal_search:
            queryset = queryset.filter(
                Q(name__icontains=universal_search) |
                Q(email__icontains=universal_search) |
                Q(phone__icontains=universal_search)
            )
        
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        ninety_days_ago = today - timedelta(days=90)
        
        avg_spending_subquery = Customer.objects.filter(
            user=self.request.user
        ).aggregate(
            avg_total=Coalesce(
                Avg('transactions_customer__sale_price',
                    filter=Q(transactions_customer__transaction_type='sale')),
                Value(0, output_field=DecimalField())
            )
        )['avg_total'] or 0
        
        high_value_threshold = float(avg_spending_subquery) * 1.5 if avg_spending_subquery else 1000
        
        queryset = queryset.annotate(
            orders_count=Count('transactions_customer', distinct=True),
            last_purchase_date=Max('transactions_customer__date'),
            total_spending=Coalesce(
                Sum('transactions_customer__sale_price', 
                    filter=Q(transactions_customer__transaction_type='sale'),
                    output_field=DecimalField()), 
                Value(0, output_field=DecimalField())
            ),

            follow_up=Case(
                When(
                    orders_count=0,
                    then=Value(True)
                ),
                When(
                    Q(last_purchase_date__lt=thirty_days_ago) & Q(orders_count__gt=0),
                    then=Value(True)
                ),
                When(
                    last_purchase_date__gte=thirty_days_ago,
                    then=Value(False)
                ),
                default=Value(True),
                output_field=BooleanField()
            ),
            
            is_active_customer=Case(
                When(
                    Q(last_purchase_date__lt=ninety_days_ago) & Q(orders_count__gt=0),
                    then=Value(False)
                ),
                When(
                    Q(last_purchase_date__gte=ninety_days_ago) & Q(orders_count__gt=0),
                    then=Value(True)
                ),
                When(
                    orders_count=0,
                    then=Value(True)
                ),
                default=Value(True),
                output_field=BooleanField()
            ),
            
            customer_tags=Case(
                When(
                    orders_count=0,
                    then=Value('Potential')
                ),
                
                When(
                    Q(last_purchase_date__lt=ninety_days_ago) & 
                    Q(orders_count__gt=0),
                    then=Value('Inactive')
                ),
                
                # 3. At Risk customers (30-90 days since last purchase)
                When(
                    Q(last_purchase_date__lt=thirty_days_ago) & 
                    Q(last_purchase_date__gte=ninety_days_ago) &
                    Q(orders_count__gt=0),
                    then=Value('At Risk')
                ),
                
                # 4. VIP customers (highest value + frequent + recent)
                When(
                    Q(total_spending__gt=high_value_threshold * 2) & 
                    Q(orders_count__gt=5) &
                    Q(last_purchase_date__gte=thirty_days_ago),
                    then=Value('VIP')
                ),
                
                # 5. High Value customers (high spending + recent purchase)
                When(
                    Q(total_spending__gt=high_value_threshold) & 
                    Q(last_purchase_date__gte=thirty_days_ago),
                    then=Value('High Value')
                ),
                
                # 6. Repeat buyers (4+ orders + recent activity)
                When(
                    Q(orders_count__gte=4) &
                    Q(last_purchase_date__gte=thirty_days_ago),
                    then=Value('Repeat Buyer')
                ),
                
                # 7. New customers (exactly 1 order + recent)
                When(
                    Q(orders_count=1) & 
                    Q(last_purchase_date__gte=thirty_days_ago),
                    then=Value('New Customer')
                ),
                
                # 8. Regular customers (2-3 orders + recent activity)
                When(
                    Q(orders_count__gte=2) &
                    Q(orders_count__lte=3) &
                    Q(last_purchase_date__gte=thirty_days_ago),
                    then=Value('Regular')
                ),
                
                # 9. Fallback for any remaining active customers
                When(
                    Q(orders_count__gt=0) &
                    Q(last_purchase_date__gte=thirty_days_ago),
                    then=Value('Active')
                ),
                
                default=Value('Untagged'),
                output_field=CharField(max_length=20)
            )
        )
        
        # Apply filters - Use the model's status field, not calculated field
        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter.lower() in ('active', 'true', '1'):
                queryset = queryset.filter(status=True)
            elif status_filter.lower() in ('inactive', 'false', '0'):
                queryset = queryset.filter(status=False)
        
        # Spending filters
        min_spending = self.request.query_params.get('min_spending')
        max_spending = self.request.query_params.get('max_spending')
        if min_spending:
            queryset = queryset.filter(total_spending__gte=min_spending)
        if max_spending:
            queryset = queryset.filter(total_spending__lte=max_spending)
        
        # Order count filters
        min_orders = self.request.query_params.get('min_orders')
        max_orders = self.request.query_params.get('max_orders')
        if min_orders:
            queryset = queryset.filter(orders_count__gte=min_orders)
        if max_orders:
            queryset = queryset.filter(orders_count__lte=max_orders)
        
        # Follow up filter
        follow_up_filter = self.request.query_params.get('follow_up')
        if follow_up_filter:
            if follow_up_filter.lower() in ('yes', 'true', '1'):
                queryset = queryset.filter(follow_up=True)
            elif follow_up_filter.lower() in ('no', 'false', '0'):
                queryset = queryset.filter(follow_up=False)
        
        # Customer tag filter
        tag_filter = self.request.query_params.get('customer_tag')
        if tag_filter:
            queryset = queryset.filter(customer_tags=tag_filter)
        
        # Activity status filter (new filter for 90-day rule)
        activity_filter = self.request.query_params.get('activity_status')
        if activity_filter:
            if activity_filter.lower() in ('active', 'true', '1'):
                queryset = queryset.filter(is_active_customer=True)
            elif activity_filter.lower() in ('inactive', 'false', '0'):
                queryset = queryset.filter(is_active_customer=False)
                
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
    
    @action(detail=False, methods=['post'])
    def update_customer_statuses(self, request):
        """
        Update all customer statuses based on 90-day purchase rule
        """
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        
        # Get customers with their last purchase dates
        customers_with_purchase_data = Customer.objects.filter(
            user=request.user
        ).annotate(
            last_purchase=Max('transactions_customer__date'),
            has_purchases=Count('transactions_customer')
        )
        
        updated_count = 0
        
        for customer in customers_with_purchase_data:
            new_status = True  # Default to active
            
            # If customer has purchases, check the 90-day rule
            if customer.has_purchases > 0 and customer.last_purchase:
                if customer.last_purchase < ninety_days_ago:
                    new_status = False  # Inactive if last purchase > 90 days
            
            # Update only if status changed
            if customer.status != new_status:
                customer.status = new_status
                customer.save(update_fields=['status'])
                updated_count += 1
        
        return Response({
            'message': f'Updated {updated_count} customer statuses based on 90-day rule',
            'updated_count': updated_count
        })
    
    @action(detail=True, methods=['patch'])
    def update_status_by_activity(self, request, pk=None):
        """
        Update individual customer status based on purchase activity
        """
        customer = self.get_object()
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        
        # Get last purchase date
        last_purchase = customer.transactions_customer.aggregate(
            last_date=Max('date')
        )['last_date']
        
        if last_purchase and last_purchase < ninety_days_ago:
            customer.status = False  # Inactive
            message = f'{customer.name} marked as inactive (last purchase: {last_purchase})'
        else:
            customer.status = True   # Active
            message = f'{customer.name} marked as active (last purchase: {last_purchase or "Never"})'
        
        customer.save(update_fields=['status'])
        
        serializer = self.get_serializer(customer)
        return Response({
            'message': message,
            'customer': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def mark_for_follow_up(self, request, pk=None):
        """
        Create a follow-up task for this customer
        """
        customer = self.get_object()
        
        # Create a follow-up entry
        due_date = request.data.get('due_date', timezone.now().date() + timedelta(days=7))
        notes = request.data.get('notes', f'Follow up with {customer.name}')
        
        follow_up = FollowUp.objects.create(
            user=request.user,
            customer=customer,
            due_date=due_date,
            notes=notes,
            status='pending'
        )
        
        return Response({
            'message': f'Follow-up scheduled for {customer.name}',
            'follow_up_id': follow_up.id,
            'due_date': follow_up.due_date,
            'notes': follow_up.notes
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        
        total_customers = queryset.count()
        active_customers = queryset.filter(is_active_customer=True).count()
        inactive_customers = queryset.filter(is_active_customer=False).count()
        customers_needing_followup = queryset.filter(follow_up=True).count()
        
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
        
        tag_stats = queryset.values('customer_tags').annotate(
            count=Count('customer_tags')
        ).order_by('-count')
        
        data = {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'inactive_customers': inactive_customers,
            'customers_needing_followup': customers_needing_followup,
            'total_spending': total_spending,
            'average_spending': avg_spending,
            'top_spenders': list(top_spenders),
            'tag_distribution': list(tag_stats),
            'note': 'Active/Inactive based on calculated 90-day rule, not model status field'
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
    def customers_needing_followup(self, request):
        """
        Get all customers that need follow-up
        """
        queryset = self.get_queryset().filter(follow_up=True)
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'customers': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def inactive_customers(self, request):
        """
        Get customers who haven't purchased in 90+ days
        """
        queryset = self.get_queryset().filter(is_active_customer=False)
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'customers': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'message': 'Export functionality placeholder',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def tag_filters(self, request):
        """
        Get available customer tags for filtering
        """
        queryset = self.get_queryset()
        available_tags = queryset.values_list('customer_tags', flat=True).distinct()
        
        return Response({
            'available_tags': [tag for tag in available_tags if tag],
            'tag_descriptions': {
                'VIP': 'Top-tier customers with highest spending (2x threshold) and 5+ orders with recent activity',
                'High Value': 'Customers with above-average spending and recent purchases',
                'Repeat Buyer': 'Loyal customers with 4+ orders and recent activity',
                'New Customer': 'Recent customers with exactly 1 purchase in the last 30 days',
                'Regular': 'Customers with 2-3 orders and recent activity',
                'Active': 'Other customers with recent purchase activity',
                'Inactive': 'Customers with no purchases in the last 90 days',
                'At Risk': 'Customers who haven\'t purchased in 30-90 days',
                'Potential': 'Prospects with contact information but no purchases yet'
            }
        })
    
class CustomerTransactionsAPIView(generics.ListAPIView):
    serializer_class = TransactionHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        return TransactionHistory.objects.filter(
            customer_id=customer_id,
            user=self.request.user
        ).prefetch_related('transaction_items', 'transaction_items__product').order_by('-date')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Add customer information to the response
        customer_id = self.kwargs.get('customer_id')
        try:
            customer = Customer.objects.get(id=customer_id, user=request.user)
            response_data = {
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'email': customer.email,
                    'phone': customer.phone,
                },
                'transactions': serializer.data
            }
            return Response(response_data)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=404)
        
class CustomerDashboardMetricsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Total Customers
        total_customers = Customer.objects.filter(user=user).count()
        
        # Average Spending - Fixed calculation using TransactionItem properly
        from django.db.models import Sum, F
        
        # Method 1: Calculate total spending per customer using database aggregation
        customer_spending = TransactionHistory.objects.filter(
            user=user,
            transaction_type='sale',
            customer__isnull=False  # Only transactions with customers
        ).values('customer').annotate(
            total_spent=Sum(
                F('transaction_items__quantity') * F('transaction_items__sale_price'),
                output_field=models.DecimalField()
            )
        ).aggregate(
            avg_spending=Avg('total_spent')
        )['avg_spending']
        
        # Get the actual average spending amount
        avg_spending_amount = float(customer_spending or 0)
        
        # Set target based on your business logic (you can adjust this)
        # Option 1: Fixed target
        target_spending = 50000  # Set your target amount
        
        # Option 2: Dynamic target based on historical data (uncomment if preferred)
        # target_spending = avg_spending_amount * 1.2 if avg_spending_amount > 0 else 10000
        
        # Calculate percentage of target achieved
        avg_spending_percent = (avg_spending_amount / target_spending * 100) if target_spending > 0 else 0
        
        # Final value to return (as percentage)
        avg_spending = round(avg_spending_percent, 2)
        
        # Alternative: If the above doesn't work due to model structure, use this approach
        # customer_totals = {}
        # for customer in Customer.objects.filter(user=user):
        #     total_spent = sum(
        #         transaction.total_sale_price 
        #         for transaction in customer.transactions_customer.filter(transaction_type='sale')
        #     )
        #     if total_spent > 0:
        #         customer_totals[customer.id] = total_spent
        # 
        # avg_spending_amount = sum(customer_totals.values()) / len(customer_totals) if customer_totals else 0
        # avg_spending_percent = (avg_spending_amount / target_spending * 100) if target_spending > 0 else 0
        # avg_spending = round(avg_spending_percent, 2)
        
        # Follow-ups due
        follow_ups_due = FollowUp.objects.filter(
            user=user,
            status='pending',
            due_date__lte=timezone.now().date()
        ).count()
        
        # New leads this month
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_leads_this_month = Customer.objects.filter(
            user=user,
            created_at__gte=start_of_month
        ).count()
        
        # Additional useful metrics (optional)
        # total_revenue = sum(customer_totals.values()) if customer_totals else 0
        # customers_with_purchases = len(customer_totals)
        
        data = {
            'total_customers': total_customers,
            'avg_spending': round(avg_spending, 2),
            'follow_ups_due': follow_ups_due,
            'new_leads_this_month': new_leads_this_month
        }
        
        serializer = DashboardMetricsSerializer(data)
        return Response(serializer.data)
    
class CustomerOrderListView(generics.ListAPIView):
    """
    API to fetch all orders/transactions for a specific customer
    """
    serializer_class = CustomerOrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        customer_id = self.kwargs.get('customer_id')
        
        # Verify customer belongs to the authenticated user
        customer = get_object_or_404(
            Customer, 
            id=customer_id, 
            user=self.request.user
        )
        
        # Get all transactions for this customer with related items
        queryset = TransactionHistory.objects.filter(
            customer=customer,
            user=self.request.user
        ).select_related(
            'customer'
        ).prefetch_related(
            Prefetch(
                'transaction_items',
                queryset=TransactionItem.objects.select_related('product')
            )
        ).order_by('-date', '-created_at')
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        customer_id = self.kwargs.get('customer_id')
        
        try:
            customer = Customer.objects.get(
                id=customer_id, 
                user=request.user
            )
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Add customer info and summary statistics
        total_orders = queryset.count()
        total_sales_amount = sum(
            transaction.total_sale_price 
            for transaction in queryset 
            if transaction.transaction_type == 'sale'
        )
        
        response_data = {
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'phone': customer.phone,
            },
            'summary': {
                'total_orders': total_orders,
                'total_sales_amount': float(total_sales_amount),
            },
            'orders': serializer.data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
def send_mass_mail(email_data_list, fail_silently=False):
    """
    Custom function to send mass emails
    
    Args:
        email_data_list: List of tuples (subject, message, from_email, recipient_list)
        fail_silently: If True, won't raise exceptions on email failures
    
    Returns:
        dict: Results of email sending operation
    """
    results = {
        'sent_count': 0,
        'failed_count': 0,
        'failed_emails': []
    }
    
    for email_data in email_data_list:
        try:
            subject, message, from_email, recipient_list = email_data
            
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipient_list
            )
            
            email.send()
            results['sent_count'] += 1
            
        except Exception as e:
            results['failed_count'] += 1
            results['failed_emails'].append({
                'recipients': recipient_list,
                'error': str(e)
            })
            
            if not fail_silently:
                logger.error(f"Failed to send email to {recipient_list}: {str(e)}")
                raise e
    
    return results


class CustomerBulkSelectView(APIView):
    """
    API to get customers for bulk selection with filters
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Query parameters for filtering
        status_filter = request.GET.get('status', 'all')  # all, active, inactive
        tag_filter = request.GET.get('tag', None)
        last_purchase_filter = request.GET.get('last_purchase', None)  # 30, 60, 90 days
        spending_filter = request.GET.get('spending', None)  # low, medium, high
        
        # Base queryset
        queryset = Customer.objects.filter(user=user)
        
        # Apply filters
        if status_filter == 'active':
            queryset = queryset.filter(status=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(status=False)
        
        if tag_filter:
            queryset = queryset.filter(tags__id=tag_filter)
        
        if last_purchase_filter:
            days = int(last_purchase_filter)
            cutoff_date = timezone.now().date() - timedelta(days=days)
            queryset = queryset.filter(
                transactions_customer__date__gte=cutoff_date,
                transactions_customer__transaction_type='sale'
            ).distinct()
        
        # Add spending annotation for filtering
        from django.db.models import Sum, Q, DecimalField
        from django.db.models.functions import Coalesce
        from decimal import Decimal
        
        queryset = queryset.annotate(
            total_spent=Coalesce(
                Sum('transactions_customer__sale_price', 
                    filter=Q(transactions_customer__transaction_type='sale')), 
                Decimal('0'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        
        if spending_filter:
            avg_spending = queryset.aggregate(avg=Coalesce(Sum('total_spent'), Decimal('0')))['avg'] or Decimal('0')
            if spending_filter == 'high':
                queryset = queryset.filter(total_spent__gt=avg_spending)
            elif spending_filter == 'low':
                queryset = queryset.filter(total_spent__lt=avg_spending / 2)
            elif spending_filter == 'medium':
                queryset = queryset.filter(
                    total_spent__gte=avg_spending / 2,
                    total_spent__lte=avg_spending
                )
        
        # Serialize the data
        serializer = CustomerBulkSerializer(queryset, many=True)
        
        return Response({
            'customers': serializer.data,
            'total_count': queryset.count(),
            'filters_applied': {
                'status': status_filter,
                'tag': tag_filter,
                'last_purchase_days': last_purchase_filter,
                'spending_level': spending_filter
            }
        })


class CustomerBulkActionsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = BulkActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        customer_ids = serializer.validated_data['customer_ids']
        action = serializer.validated_data['action']
        action_data = serializer.validated_data.get('action_data', {})
        
        customers = Customer.objects.filter(
            id__in=customer_ids,
            user=request.user
        )
        
        if customers.count() != len(customer_ids):
            return Response(
                {'error': 'Some customers not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            with transaction.atomic():
                result = self._perform_bulk_action(customers, action, action_data, request.user)
                return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk action failed: {str(e)}")
            return Response(
                {'error': f'Action failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _perform_bulk_action(self, customers, action, action_data, user):
        results = {
            'action': action,
            'processed_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        if action == 'deactivate':
            updated = customers.update(status=False)
            results['processed_count'] = updated
            results['message'] = f'{updated} customers deactivated successfully'
        
        elif action == 'activate':
            updated = customers.update(status=True)
            results['processed_count'] = updated
            results['message'] = f'{updated} customers activated successfully'
        
        elif action == 'mark_follow_up':
            due_date = action_data.get('due_date')
            notes = action_data.get('notes', '')
            
            if not due_date:
                raise ValueError("Due date is required for follow-up action")
            
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            
            follow_ups_created = []
            for customer in customers:
                follow_up, created = FollowUp.objects.get_or_create(
                    user=user,
                    customer=customer,
                    due_date=due_date,
                    defaults={'notes': notes, 'status': 'pending'}
                )
                if created:
                    follow_ups_created.append(follow_up)
                    results['processed_count'] += 1
                else:
                    results['failed_count'] += 1
                    results['details'].append(f'Follow-up already exists for {customer.name}')
            
            results['message'] = f'{len(follow_ups_created)} follow-ups created successfully'
        
        elif action == 'add_tag':
            tag_id = action_data.get('tag_id')
            if not tag_id:
                raise ValueError("Tag ID is required")
            
            try:
                tag = CustomerTag.objects.get(id=tag_id, user=user)
                for customer in customers:
                    tag.customers.add(customer)
                    results['processed_count'] += 1
                results['message'] = f'Tag "{tag.name}" added to {results["processed_count"]} customers'
            except CustomerTag.DoesNotExist:
                raise ValueError("Tag not found")
        
        elif action == 'remove_tag':
            tag_id = action_data.get('tag_id')
            if not tag_id:
                raise ValueError("Tag ID is required")
            
            try:
                tag = CustomerTag.objects.get(id=tag_id, user=user)
                for customer in customers:
                    tag.customers.remove(customer)
                    results['processed_count'] += 1
                results['message'] = f'Tag "{tag.name}" removed from {results["processed_count"]} customers'
            except CustomerTag.DoesNotExist:
                raise ValueError("Tag not found")
        
        elif action == 'send_newsletter':
            subject = action_data.get('subject', 'Newsletter')
            message = action_data.get('message', '')
            
            if not message:
                raise ValueError("Message content is required for newsletter")
            
            # Prepare mass email data
            emails_to_send = []
            for customer in customers:
                if customer.email:
                    emails_to_send.append((
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [customer.email]
                    ))
                else:
                    results['failed_count'] += 1
                    results['details'].append(f'No email address for {customer.name}')
            
            # Send mass email using custom function
            if emails_to_send:
                try:
                    email_results = send_mass_mail(emails_to_send, fail_silently=False)
                    results['processed_count'] = email_results['sent_count']
                    results['failed_count'] += email_results['failed_count']
                    
                    if email_results['failed_emails']:
                        for failed_email in email_results['failed_emails']:
                            results['details'].append(f'Failed to send to {failed_email["recipients"]}: {failed_email["error"]}')
                    
                    results['message'] = f'Newsletter sent to {email_results["sent_count"]} customers'
                    if email_results['failed_count'] > 0:
                        results['message'] += f', {email_results["failed_count"]} failed'
                        
                except Exception as e:
                    raise ValueError(f'Failed to send emails: {str(e)}')
            else:
                results['message'] = 'No customers with valid email addresses'
        
        elif action == 'delete':
            # Hard delete - permanently remove from database
            count = customers.count()
            deleted_info = customers.delete()
            results['processed_count'] = count
            results['message'] = f'{count} customers permanently deleted from database'
            results['details'].append(f'Deletion details: {deleted_info}')
        
        else:
            raise ValueError(f"Unknown action: {action}")
        
        return results