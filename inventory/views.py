from rest_framework import viewsets, permissions, generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from .models import Brand, WatchModel, Watch
from .serializers import BrandSerializer, WatchModelSerializer, WatchSerializer
from django.db.models import Count, Sum, Avg

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

class WatchModelViewSet(viewsets.ModelViewSet):
    queryset = WatchModel.objects.all()
    serializer_class = WatchModelSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand']
    search_fields = ['name', 'reference_number', 'brand__name']
    ordering_fields = ['name', 'brand__name']

class WatchViewSet(viewsets.ModelViewSet):
    serializer_class = WatchSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'condition', 'watch_model__brand']
    search_fields = ['serial_number', 'watch_model__name', 'watch_model__brand__name']
    ordering_fields = ['purchase_date', 'asking_price', 'purchase_price']
    queryset = Watch.objects.all()
    
    def get_queryset(self):
        # Filter watches by the current user
        return Watch.objects.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        # Set the owner to the current user
        serializer.save(owner=self.request.user)

class InventoryStatsView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request):
        # Get user's inventory stats
        watches = Watch.objects.filter(owner=request.user)
        
        # Total inventory value
        total_inventory_value = watches.filter(status='in_stock').aggregate(
            total_purchase=Sum('purchase_price'),
            total_asking=Sum('asking_price')
        )