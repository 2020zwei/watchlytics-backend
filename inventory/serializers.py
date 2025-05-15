from rest_framework import serializers
from .models import Category, Product
from django.utils import timezone
from datetime import datetime
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

class ProductSerializer(serializers.ModelSerializer):
    # days_in_inventory = serializers.ReadOnlyField()
    is_sold = serializers.ReadOnlyField()
    profit = serializers.SerializerMethodField()
    profit_margin = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    date_purchased = serializers.DateTimeField(format="%Y-%m-%d")
    date_sold = serializers.DateTimeField(format="%Y-%m-%d", required=False, allow_null=True)
    hold_time = serializers.SerializerMethodField()
    # reference_number = serializers.SerializerMethodField()
    class Meta:
        model = Product
        fields = [
            'id', 'owner', 'quantity', 'product_id', 'model_name', 'date_purchased', 'date_sold',
            'hold_time', 'source_of_sale', 'brand', 'category',
            'buying_price',  'sold_price', 'wholesale_price','profit', 'profit_margin',
            'shipping_price', 'repair_cost', 'fees', 'commission',
            'msrp', 'website_price', 'purchased_from', 'sold_source', 'listed_on',
            'image', 'is_sold', 'availability', 'condition',
            'serial_number', 'year'
        ]
        read_only_fields = ['created_at', 'updated_at', 'owner']

    def get_brand(self, obj):
        return obj.category.name if obj.category else None
    
    def get_hold_time(self, obj):
        if not obj.date_purchased:
            return None

        start_date = obj.date_purchased
        end_date = obj.date_sold or timezone.now()

        return (end_date - start_date).days
    
    def get_profit(self, obj):
        if not obj.sold_price:
            return None
            
        total_cost = obj.buying_price or 0
        total_cost += obj.shipping_price or 0
        total_cost += obj.repair_cost or 0
        total_cost += obj.fees or 0
        total_cost += obj.commission or 0
        
        profit = obj.sold_price - total_cost
        
        return round(profit, 2)
    
    def get_profit_margin(self, obj):
        if not obj.sold_price or not obj.buying_price:
            return None
            
        total_cost = obj.buying_price or 0
        total_cost += obj.shipping_price or 0
        total_cost += obj.repair_cost or 0
        total_cost += obj.fees or 0
        total_cost += obj.commission or 0
        
        if total_cost == 0:
            return None
            
        profit = obj.sold_price - total_cost
        profit_margin = (profit / total_cost) * 100
        
        return round(profit_margin, 2)
    
class ProductCreateSerializer(serializers.ModelSerializer):
    date_purchased = serializers.DateTimeField(
        input_formats=[
            '%Y-%m-%dT%H:%M:%S.%fZ',  
            '%Y-%m-%dT%H:%M:%SZ',     
            '%Y-%m-%d %H:%M:%S',     
            '%m/%d/%Y %H:%M:%S',
            '%d-%m-%Y %H:%M:%S',
            '%Y-%m-%d',         
        ],
        format='%Y-%m-%d',
    )

    date_sold = serializers.DateTimeField(
        input_formats=[
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%d-%m-%Y %H:%M:%S',
            '%Y-%m-%d',
        ],
        format='%Y-%m-%d',
        required=False,
        allow_null=True
    )
    class Meta:
        model = Product
        fields = [
            'model_name', 'product_id', 'category',
            'buying_price', 'shipping_price', 'repair_cost', 'fees', 'commission',
            'msrp', 'wholesale_price', 'website_price', 'profit', 'profit_margin', 'year',
            'quantity', 'unit', 'date_purchased', 'hold_time', 'sold_price', 'source_of_sale',
            'purchased_from', 'listed_on', 'image', 'availability', 
            'sold_source', 'date_sold', 'serial_number',
        ]
    
    def validate_category(self, value):
        if not Category.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Category does not exist")
        return value
    
    def validate(self, data):
        if 'buying_price' in data and data['buying_price'] <= 0:
            raise serializers.ValidationError({"buying_price": "Buying price must be greater than 0"})
        
        return data
    
class ProductCSVUploadSerializer(serializers.Serializer):
    csv_file = serializers.FileField()