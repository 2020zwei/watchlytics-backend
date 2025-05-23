from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.db.models import Avg, Min, Max, Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import Lower
from django.core.paginator import Paginator
from .models import MarketData
from .serializers import MarketDataSerializer

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'results': data
        })

class MarketDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MarketData.objects.all()
    serializer_class = MarketDataSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source', 'brand', 'reference_number', 'condition']
    search_fields = ['name', 'reference_number', 'brand']
    ordering_fields = ['price', 'scraped_at', 'listing_date']
    
    @action(detail=False, methods=['get'])
    def group_by_reference(self, request):
        # Get pagination parameters
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        
        queryset = self.filter_queryset(self.get_queryset())
        reference_numbers_query = queryset.values_list('reference_number', flat=True).distinct().exclude(reference_number__isnull=True).exclude(reference_number='')
        paginator = Paginator(reference_numbers_query, page_size)
        page_obj = paginator.get_page(page)
        
        grouped_data = []
        
        for ref_num in page_obj.object_list:
            ref_data = queryset.filter(reference_number=ref_num).select_related()
            
            stats = ref_data.aggregate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
                count=Count('id')
            )
            
            sample = ref_data.first()
            if not sample:
                continue
            
            sources = list(ref_data.values_list('source', flat=True).distinct())
            
            grouped_data.append({
                'reference_number': ref_num,
                'brand': sample.brand,
                'count': stats['count'],
                'avg_price': round(stats['avg_price'], 2) if stats['avg_price'] else None,
                'min_price': stats['min_price'],
                'max_price': stats['max_price'],
                'sources': sources,
                'sample_image': sample.image_url,
                'sample_name': sample.name,
            })
        
        return Response({
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page,
            'page_size': page_size,
            'results': grouped_data
        })
    
    @action(detail=False, methods=['get'])
    def market_comparison(self, request):
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        
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
                Q(name__icontains=search_query) | 
                Q(reference_number__icontains=search_query) |
                Q(brand__icontains=search_query)
            )
        
        distinct_watches_query = queryset.exclude(
            reference_number__isnull=True
        ).exclude(
            reference_number=''
        ).values(
            'reference_number', 'brand'
        ).annotate(
            lower_brand=Lower('brand')
        ).order_by('lower_brand', 'reference_number').distinct()
        
        paginator = Paginator(distinct_watches_query, page_size)
        page_obj = paginator.get_page(page)
        
        comparison_data = []
        
        for watch in page_obj.object_list:
            ref_num = watch['reference_number']
            
            watch_data = queryset.filter(reference_number=ref_num).select_related()
            
            sample = watch_data.first()
            if not sample:
                continue
            
            buying_price = watch_data.aggregate(avg_price=Avg('price'))['avg_price']
            
            sources_data = {
                'ebay': {'price': None, 'trend': None},
                'chrono24': {'price': None, 'trend': None},
                'bezel': {'price': None, 'trend': None},
                'grailzee': {'price': None, 'trend': None}
            }
            
            for source in ['ebay', 'chrono24', 'bezel', 'grailzee']:
                source_data = watch_data.filter(source=source).order_by('-scraped_at').first()
                if source_data and buying_price:
                    trend = None
                    if source_data.price > buying_price:
                        trend = 'up'
                    elif source_data.price < buying_price:
                        trend = 'down'
                    else:
                        trend = 'stable'
                    
                    sources_data[source] = {
                        'price': source_data.price,
                        'trend': trend
                    }
            
            comparison_item = {
                'reference_number': ref_num,
                'brand': sample.brand,
                'name': sample.name,
                'image_url': sample.image_url,
                'buying_price': round(buying_price, 2) if buying_price else None,
                'sources': sources_data
            }
            
            comparison_data.append(comparison_item)
        
        return Response({
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page,
            'page_size': page_size,
            'results': comparison_data
        })

    @action(detail=False, methods=['get'])
    def summary_stats(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        
        stats = {
            'total_records': queryset.count(),
            'unique_references': queryset.exclude(
                reference_number__isnull=True
            ).exclude(
                reference_number=''
            ).values('reference_number').distinct().count(),
            'unique_brands': queryset.exclude(
                brand__isnull=True
            ).exclude(
                brand=''
            ).values('brand').distinct().count(),
            'price_range': queryset.aggregate(
                min_price=Min('price'),
                max_price=Max('price'),
                avg_price=Avg('price')
            ),
            'sources': list(queryset.values_list('source', flat=True).distinct())
        }
        
        return Response(stats)