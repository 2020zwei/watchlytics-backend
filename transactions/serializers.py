from rest_framework import serializers
from .models import TransactionHistory
from customers.models import Customer
from inventory.models import Product


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name']


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'product_name', 'buying_price']


class TransactionHistorySerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    profit = serializers.SerializerMethodField()
    
    class Meta:
        model = TransactionHistory
        fields = [
            'id', 'transaction_type', 'product', 'product_name', 'amount', 
            'date', 'notes', 'sale_category', 'customer', 'customer_name',
            'expenses', 'profit', 'created_at', 'updated_at'
        ]
    
    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.name
        return None
    
    def get_product_name(self, obj):
        if obj.product:
            return obj.product.product_name
        return None
    
    def get_profit(self, obj):
        if obj.transaction_type == 'sale':
            return obj.profit
        return None


class TransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionHistory
        fields = [
            'product', 'transaction_type', 'amount', 'date', 
            'notes', 'sale_category', 'customer', 'expenses'
        ]
    
    def validate(self, data):
        if data.get('transaction_type') == 'sale' and not data.get('sale_category'):
            raise serializers.ValidationError("Sale category is required for sale transactions")
        
        expenses = data.get('expenses', {})
        if not isinstance(expenses, dict):
            raise serializers.ValidationError("Expenses must be a dictionary")
        
        for key, expense in expenses.items():
            if not isinstance(expense, dict) or 'amount' not in expense:
                raise serializers.ValidationError(f"Each expense must be a dictionary with an 'amount' key")
            
            try:
                float(expense['amount'])
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Expense amount must be a number")
        
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)