import django_filters
from .models import MarketData

class MarketDataFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    scraped_after = django_filters.DateTimeFilter(field_name='scraped_at', lookup_expr='gte')
    scraped_before = django_filters.DateTimeFilter(field_name='scraped_at', lookup_expr='lte')
    
    class Meta:
        model = MarketData
        fields = ['source', 'brand', 'reference_number', 'condition', 
                  'min_price', 'max_price', 'scraped_after', 'scraped_before']