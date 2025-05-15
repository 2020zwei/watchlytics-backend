from rest_framework import serializers
from .models import Invoice
from auth_.models import User
from transactions.models import TransactionHistory

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def validate(self, data):
        if 'due_date' in data and 'issue_date' in data:
            if data['due_date'] < data['issue_date']:
                raise serializers.ValidationError("Due date must be after issue date")
        
        if 'subtotal' in data and 'tax_amount' in data and 'total' not in data:
            data['total'] = data['subtotal'] + data['tax_amount']
            
        return data

class InvoiceDetailSerializer(InvoiceSerializer):
    user = serializers.StringRelatedField()
    transaction_history = serializers.StringRelatedField()
    
    class Meta(InvoiceSerializer.Meta):
        depth = 1