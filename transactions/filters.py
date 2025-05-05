import django_filters
from .models import TransactionHistory
from django.db.models import Q

class TransactionHistoryFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    class Meta:
        model = TransactionHistory
        fields = [
            'transaction_type', 'sale_category', 'customer', 'product',
            'start_date', 'end_date', 'min_amount', 'max_amount'
        ]