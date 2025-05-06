from rest_framework import serializers
from .models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

class ProductSerializer(serializers.ModelSerializer):
    days_in_inventory = serializers.ReadOnlyField()
    is_sold = serializers.ReadOnlyField()
    calculated_profit = serializers.ReadOnlyField()
    category_name = serializers.SerializerMethodField()
    date_purchased = serializers.DateTimeField(format="%Y-%m-%d")
    date_sold = serializers.DateTimeField(format="%Y-%m-%d", required=False, allow_null=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'owner', 'product_name', 'product_id', 'category_name', 'category',
            'buying_price', 'shipping_price', 'repair_cost', 'fees', 'commission',
            'msrp', 'sold_price', 'whole_price', 'website_price', 'profit_margin',
            'quantity', 'unit', 'date_purchased', 'date_sold', 'hold_time',
            'source_of_sale', 'purchased_from', 'sold_source', 'listed_on',
            'image', 'days_in_inventory', 'is_sold', 'availability', 'condition',
            'calculated_profit', 'serial_number'
        ]
        read_only_fields = ['created_at', 'updated_at', 'owner']

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None
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
            'product_name', 'product_id', 'category',
            'buying_price', 'shipping_price', 'repair_cost', 'fees', 'commission',
            'msrp', 'whole_price', 'website_price', 'profit_margin',
            'quantity', 'unit', 'date_purchased', 'hold_time', 'sold_price', 'source_of_sale'
            'purchased_from', 'listed_on', 'image', 'availability', 'date_sold', 'serial_number',
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