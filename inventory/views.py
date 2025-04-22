from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer, ProductCreateSerializer
from rest_framework.permissions import AllowAny


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Product.objects.filter(owner=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProductCreateSerializer
        return ProductSerializer
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_product(self, request):
        serializer = ProductCreateSerializer(data=request.data, files=request.FILES)
        if serializer.is_valid():
            product = serializer.save(owner=request.user)
            response_serializer = ProductSerializer(product)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def unsold(self, request):
        unsold_products = self.get_queryset().filter(date_sold__isnull=True)
        serializer = self.get_serializer(unsold_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def sold(self, request):
        sold_products = self.get_queryset().filter(date_sold__isnull=False)
        serializer = self.get_serializer(sold_products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def mark_as_sold(self, request, pk=None):
        product = self.get_object()
        sold_data = {
            'date_sold': request.data.get('date_sold', timezone.now().date()),
            'sold_price': request.data.get('sold_price'),
            'sold_source': request.data.get('sold_source'),
            'status': 'sold'
        }
        
        serializer = self.get_serializer(product, data=sold_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    @action(detail=True, methods=['put', 'patch'])
    def update_product(self, request, pk=None):
        try:
            product = self.get_object()
            
            # Choose appropriate serializer based on update type
            if request.method == 'PUT':
                serializer = ProductSerializer(product, data=request.data)
            else:
                serializer = ProductSerializer(product, data=request.data, partial=True)
            
            if serializer.is_valid():
                if 'buying_price' in request.data and float(request.data['buying_price']) <= 0:
                    return Response(
                        {"buying_price": "Buying price must be greater than 0"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if request.data.get('status') == 'sold' and not request.data.get('sold_price'):
                    return Response(
                        {"sold_price": "Sold price is required when marking a product as sold"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                updated_product = serializer.save()
                response_serializer = ProductSerializer(updated_product)
                return Response(response_serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
        except Exception as e:
            return Response(
                {"error": f"Failed to update product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_product(self, request, pk=None):
        try:
            product = self.get_object()
            
            # if product.orders.exists():
            #     return Response(
            #         {"error": "Cannot delete product that is referenced by orders"},
            #         status=status.HTTP_400_BAD_REQUEST
            #     )
            
            # Standard deletion
            product_name = product.product_name
            product.delete()
            
            return Response(
                {"message": f"Product '{product_name}' successfully deleted"},
                status=status.HTTP_204_NO_CONTENT
            )
        
        except Exception as e:
            return Response(
                {"error": f"Failed to delete product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )