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
from inventory.models import Product  # Import Product model from inventory

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
    def inventory_based_comparison(self, request):
        """
        New endpoint that compares market data based on user's inventory
        """
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        user = request.user
        
        brand_filter = request.query_params.get('brand')
        reference_number_filter = request.query_params.get('reference_number')
        search_query = request.query_params.get('search')
        product_id_filter = request.query_params.get('product_id')
        model_name_filter = request.query_params.get('model_name')
        min_buying_price = request.query_params.get('min_buying_price')
        max_buying_price = request.query_params.get('max_buying_price')
        
        # Get user's inventory products with all necessary fields
        inventory_products = Product.objects.filter(owner=user).select_related('category')
        
        # Apply filters to inventory products
        if brand_filter:
            inventory_products = inventory_products.filter(category__name__iexact=brand_filter)
        
        if reference_number_filter:
            inventory_products = inventory_products.filter(product_id__iexact=reference_number_filter)
        
        if product_id_filter:
            inventory_products = inventory_products.filter(product_id__icontains=product_id_filter)
        
        if model_name_filter:
            inventory_products = inventory_products.filter(model_name__icontains=model_name_filter)
        
        if search_query:
            inventory_products = inventory_products.filter(
                Q(model_name__icontains=search_query) |
                Q(product_id__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )
        
        if min_buying_price:
            try:
                min_price = float(min_buying_price)
                inventory_products = inventory_products.filter(buying_price__gte=min_price)
            except (ValueError, TypeError):
                pass
        
        if max_buying_price:
            try:
                max_price = float(max_buying_price)
                inventory_products = inventory_products.filter(buying_price__lte=max_price)
            except (ValueError, TypeError):
                pass
        
        if not inventory_products.exists():
            return Response({
                'next': None,
                'previous': None,
                'count': 0,
                'total_pages': 0,
                'current_page': page,
                'page_size': page_size,
                'results': [],
                'message': 'No inventory products found for comparison with the applied filters'
            })
        
        # Paginate inventory products
        paginator = Paginator(inventory_products, page_size)
        page_obj = paginator.get_page(page)
        
        comparison_data = []
        
        for product in page_obj.object_list:
            product_id = product.product_id
            model_name = product.model_name
            buying_price = product.buying_price
            inventory_id = product.id
            product_image = product.image.url if product.image else None
            brand = product.category.name if product.category else None
            
            # Find market data matches with prioritized search strategy
            market_data = self._find_market_matches(product_id, model_name, brand)
            
            if not market_data.exists():
                # Include inventory item even if no market data found
                comparison_data.append({
                    'inventory_id': inventory_id,
                    'reference_number': product_id,
                    'model_name': model_name,
                    'name': None,
                    'image_url': product_image,
                    'brand': brand,
                    'buying_price': float(buying_price) if buying_price else None,
                    'market_matches_count': 0,
                    'market_data': {
                        'avg_price': None,
                        'min_price': None,
                        'max_price': None,
                        'sources': []
                    },
                    'sources': {},
                    'potential_profit': None,
                    'message': 'No market data found matching this product'
                })
                continue
            
            # Calculate market statistics
            market_stats = market_data.aggregate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
                count=Count('id')
            )
            
            # Get a sample market item for additional info
            sample_market_item = market_data.first()
            
            # Get sources data and compare with inventory buying price
            sources_data = {}
            sources_list = list(market_data.values_list('source', flat=True).distinct())
            
            for source in ['ebay', 'chrono24', 'bezel', 'grailzee']:
                source_items = market_data.filter(source=source)
                if source_items.exists():
                    source_stats = source_items.aggregate(
                        avg_price=Avg('price'),
                        min_price=Min('price'),
                        max_price=Max('price'),
                        count=Count('id')
                    )
                    
                    # Calculate trend based on inventory buying price vs market average
                    trend = None
                    source_avg = source_stats['avg_price']
                    if source_avg and buying_price:
                        if source_avg > float(buying_price) * 1.05:  # 5% threshold
                            trend = 'up'
                        elif source_avg < float(buying_price) * 0.95:  # 5% threshold
                            trend = 'down'
                        else:
                            trend = 'stable'

                    sources_data[source] = {
                        'avg_price': round(source_avg, 2) if source_avg else None,
                        'min_price': source_stats['min_price'],
                        'max_price': source_stats['max_price'],
                        'price': round(source_avg, 2) if source == 'ebay' and source_avg else source_stats['min_price'],
                        'count': source_stats['count'],
                        'trend': trend
                    }
            
            # Calculate potential profit based on market average vs inventory buying price
            potential_profit = None
            if market_stats['avg_price'] and buying_price:
                potential_profit = round(float(market_stats['avg_price']) - float(buying_price), 2)
            
            comparison_item = {
                'inventory_id': inventory_id,
                'reference_number': product_id,
                'model_name': model_name,
                'name': sample_market_item.name if sample_market_item else None,
                'brand': brand,
                'buying_price': float(buying_price) if buying_price else None,
                'market_matches_count': market_stats['count'],
                'image_url': product_image if product_image else sample_market_item.image_url if sample_market_item else None,
                'sources': sources_data,
                'market_data': {
                    'avg_price': round(market_stats['avg_price'], 2) if market_stats['avg_price'] else None,
                    'min_price': market_stats['min_price'],
                    'max_price': market_stats['max_price'],
                    'sources': sources_list,
                    'sample_name': sample_market_item.name if sample_market_item else None,
                    'sample_brand': sample_market_item.brand if sample_market_item else None,
                    'sample_image': sample_market_item.image_url if sample_market_item else None
                },
                'potential_profit': potential_profit,
                'profit_margin_percentage': round((potential_profit / float(buying_price)) * 100, 2) if potential_profit and buying_price else None
            }
            
            comparison_data.append(comparison_item)
        
        return Response({
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page,
            'page_size': page_size,
            'results': comparison_data,
            'applied_filters': {
                'brand': brand_filter,
                'reference_number': reference_number_filter,
                'search': search_query,
                'product_id': product_id_filter,
                'model_name': model_name_filter,
                'min_buying_price': min_buying_price,
                'max_buying_price': max_buying_price
            }
        })
    
    def _find_market_matches(self, product_id, model_name, brand):
        """
        Helper method to find market data matches with prioritized search strategy
        """
        all_matches = MarketData.objects.none()
        
        if product_id:
            product_id = product_id.strip()
            
            # Strategy 1: For sources with reference_number field (chrono24, bezel, grailzee)
            # Exact reference number match (highest priority)
            exact_ref_matches = MarketData.objects.filter(
                reference_number__iexact=product_id
            ).exclude(source='ebay')
            
            # Reference number contains product_id
            ref_contains_matches = MarketData.objects.filter(
                reference_number__icontains=product_id
            ).exclude(source='ebay')
            
            # Strategy 2: For eBay - search in name field since they don't have reference_number
            ebay_name_matches = MarketData.objects.filter(
                source='ebay',
                name__icontains=product_id
            )
            
            # Combine matches from reference_number sources and eBay name matches
            if exact_ref_matches.exists() or ref_contains_matches.exists() or ebay_name_matches.exists():
                # Use exact reference matches if available, otherwise use contains matches
                ref_matches = exact_ref_matches if exact_ref_matches.exists() else ref_contains_matches
                all_matches = ref_matches.union(ebay_name_matches) if ebay_name_matches.exists() else ref_matches
                if all_matches.exists():
                    return all_matches
        
        # Strategy 3: If no reference/name matches with product_id, try model name with brand
        if model_name and brand:
            model_brand_matches = MarketData.objects.filter(
                Q(name__icontains=model_name.strip()) & Q(brand__icontains=brand.strip())
            )
            if model_brand_matches.exists():
                return model_brand_matches
        
        # Strategy 4: Model name only (if brand matching fails)
        if model_name:
            model_matches = MarketData.objects.filter(name__icontains=model_name.strip())
            if model_matches.exists():
                return model_matches
        
        # Return empty queryset if no matches found
        return MarketData.objects.none()
    
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