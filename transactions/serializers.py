from rest_framework import serializers
from transactions.models import TransactionHistory, TransactionItem

from inventory.models import Product
from decimal import Decimal
# from customers.serializers import CustomerSerializer
from inventory.serializers import ProductSerializer

class TransactionItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = TransactionItem
        fields = ['id', 'product', 'product_details', 'quantity', 'purchase_price', 'sale_price', 
                  'total_purchase_price', 'total_sale_price']
        read_only_fields = ['total_purchase_price', 'total_sale_price']


class TransactionItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionItem
        fields = ['product', 'quantity', 'purchase_price', 'sale_price']


class TransactionHistorySerializer(serializers.ModelSerializer):
    items = TransactionItemSerializer(source='transaction_items', many=True, read_only=True)
    # customer_details = CustomerSerializer(source='customer', read_only=True)
    profit = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_sale_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    date = serializers.DateField(format="%d-%m-%Y")
    
    class Meta:
        model = TransactionHistory
        fields = [
            'id', 'user', 'name_of_trade', 'transaction_type', 'date', 'purchase_price', 'sale_price',
            'notes', 'sale_category', 'customer',
            'created_at', 'updated_at', 'items', 'profit', 'total_purchase_price', 'total_sale_price'
        ]
        read_only_fields = ['user', 'profit', 'total_purchase_price', 'total_sale_price']


class TransactionCreateSerializer(serializers.ModelSerializer):
    transaction_items = TransactionItemCreateSerializer(many=True)
    date = serializers.DateField(
        input_formats=[
            '%Y-%m-%dT%H:%M:%S.%fZ',  
            '%Y-%m-%dT%H:%M:%SZ',     
            '%Y-%m-%d %H:%M:%S',     
            '%m/%d/%Y %H:%M:%S',
            '%d-%m-%Y %H:%M:%S',
            '%Y-%m-%d',        
            '%d-%m-%y',
            '%d-%m-%Y',
        ],
    )
    
    class Meta:
        model = TransactionHistory
        fields = [
            'name_of_trade', 'transaction_type', 'date', 'purchase_price', 'sale_price',
            'notes', 'sale_category', 'customer', 'transaction_items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('transaction_items')
        user = self.context['request'].user
        
        transaction = TransactionHistory.objects.create(
            user=user,
            **validated_data
        )
        
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            item_data['purchase_price'] = Decimal(str(item_data['purchase_price']))
            item_data['sale_price'] = Decimal(str(item_data['sale_price']))
            
            TransactionItem.objects.create(
                transaction=transaction,
                **item_data
            )
            
            if transaction.transaction_type == 'purchase':
                product.quantity += quantity
            elif transaction.transaction_type == 'sale':
                product.quantity -= quantity
            product.save()
        
        return transaction
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('transaction_items', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if items_data is not None:
            for old_item in instance.transaction_items.all():
                product = old_item.product
                if instance.transaction_type == 'purchase':
                    product.quantity -= old_item.quantity
                elif instance.transaction_type == 'sale':
                    product.quantity += old_item.quantity
                product.save()
            
            instance.transaction_items.all().delete()
            
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']
                
                item_data['purchase_price'] = Decimal(str(item_data['purchase_price']))
                item_data['sale_price'] = Decimal(str(item_data['sale_price']))
                
                TransactionItem.objects.create(
                    transaction=instance,
                    **item_data
                )
                
                if instance.transaction_type == 'purchase':
                    product.quantity += quantity
                elif instance.transaction_type == 'sale':
                    product.quantity -= quantity
                product.save()
        
        return instance