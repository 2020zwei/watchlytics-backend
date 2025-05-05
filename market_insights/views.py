from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Avg, Min, Max, Count
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import Lower
from .models import MarketData
from .serializers import MarketDataSerializer

class MarketDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MarketData.objects.all()
    serializer_class = MarketDataSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source', 'brand', 'reference_number', 'condition']
    search_fields = ['name', 'reference_number', 'brand']
    ordering_fields = ['price', 'scraped_at', 'listing_date']
    
    @action(detail=False, methods=['get'])
    def group_by_reference(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        
        grouped_data = []
        reference_numbers = queryset.values_list('reference_number', flat=True).distinct()
        
        for ref_num in reference_numbers:
            if not ref_num:
                continue
                
            ref_data = queryset.filter(reference_number=ref_num)
            
            stats = ref_data.aggregate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
                count=Count('id')
            )
            
            sample = ref_data.first()
            
            grouped_data.append({
                'reference_number': ref_num,
                'brand': sample.brand,
                'count': stats['count'],
                'avg_price': stats['avg_price'],
                'min_price': stats['min_price'],
                'max_price': stats['max_price'],
                'sources': list(ref_data.values_list('source', flat=True).distinct()),
                'sample_image': sample.image_url,
                'sample_name': sample.name,
            })
            
        return Response(grouped_data)
    
    @action(detail=False, methods=['get'])
    def market_comparison(self, request):
        brand = request.query_params.get('brand')
        reference_number = request.query_params.get('reference_number')
        search_query = request.query_params.get('search')
        
        queryset = self.get_queryset()
        
        if brand:
            queryset = queryset.filter(brand__iexact=brand)
        if reference_number:
            queryset = queryset.filter(reference_number__iexact=reference_number)
        if search_query:
            queryset = queryset.filter(
                models.Q(name__icontains=search_query) | 
                models.Q(reference_number__icontains=search_query) |
                models.Q(brand__icontains=search_query)
            )
        
        comparison_data = []
        
        distinct_watches = queryset.order_by().values(
            'reference_number', 'brand'
        ).annotate(
            lower_brand=Lower('brand')
        ).order_by('lower_brand', 'reference_number').distinct()
        
        for watch in distinct_watches:
            ref_num = watch['reference_number']
            if not ref_num:
                continue
                
            watch_data = queryset.filter(reference_number=ref_num)
            
            sample = watch_data.first()
            if not sample:
                continue
                
            sources_data = {
                'ebay': {'price': None, 'trend': None},
                'chrono24': {'price': None, 'trend': None},
                'bezel': {'price': None, 'trend': None},
                'grailzee': {'price': None, 'trend': None}
            }
            
            buying_price = watch_data.aggregate(avg_price=Avg('price'))['avg_price']
            
            for source in ['ebay', 'chrono24', 'bezel', 'grailzee']:
                source_data = watch_data.filter(source=source).order_by('-scraped_at').first()
                if source_data:
                    trend = None
                    if source_data.price > buying_price:
                        trend = 'up'
                    elif source_data.price < buying_price:
                        trend = 'down'
                    
                    sources_data[source] = {
                        'price': source_data.price,
                        'trend': trend
                    }
            
            comparison_item = {
                'reference_number': ref_num,
                'brand': sample.brand,
                'name': sample.name,
                'image_url': sample.image_url,
                'buying_price': buying_price,
                'sources': sources_data
            }
            
            comparison_data.append(comparison_item)
            
        return Response(comparison_data)