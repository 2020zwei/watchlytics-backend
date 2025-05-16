from rest_framework import serializers
from .models import Invoice
from transactions.models import TransactionHistory
from transactions.serializers import TransactionHistorySerializer

class InvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'status_display', 
            'issue_date', 'due_date', 'total', 'customer_info'
        ]
        read_only_fields = ['invoice_number']
    
    def get_status_display(self, obj):
        return obj.get_status_display()


class InvoiceDetailSerializer(serializers.ModelSerializer):
    transaction_details = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'status_display', 
            'issue_date', 'due_date', 'paid_date',
            'subtotal', 'tax_amount', 'tax_rate', 'total',
            'notes', 'terms', 'company_info', 'customer_info',
            'pdf_url', 'transaction_details', 'days_overdue',
            'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        return obj.get_status_display()
    
    def get_transaction_details(self, obj):
        try:
            transaction = obj.transaction_history
            serializer = TransactionHistorySerializer(transaction)
            return serializer.data
        except:
            return None
    
    def get_days_overdue(self, obj):
        from django.utils import timezone
        
        if obj.status == 'paid' or obj.status == 'canceled':
            return 0
        
        today = timezone.now().date()
        if today > obj.due_date:
            return (today - obj.due_date).days
        return 0


class InvoiceCreateSerializer(serializers.ModelSerializer):
    transaction_history_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'transaction_history_id', 'status', 'issue_date', 'due_date',
            'subtotal', 'tax_amount', 'tax_rate', 'total',
            'notes', 'terms', 'company_info', 'customer_info'
        ]
        read_only_fields = ['invoice_number']
    
    def validate_transaction_history_id(self, value):
        try:
            transaction = TransactionHistory.objects.get(id=value)
            user = self.context['request'].user
            
            if transaction.user != user:
                raise serializers.ValidationError("This transaction does not belong to you")
            
            if hasattr(transaction, 'invoice'):
                raise serializers.ValidationError("This transaction already has an invoice")
                
            return value
        except TransactionHistory.DoesNotExist:
            raise serializers.ValidationError("Transaction not found")
    
    def create(self, validated_data):
        transaction_id = validated_data.pop('transaction_history_id')
        transaction = TransactionHistory.objects.get(id=transaction_id)
        
        if 'subtotal' not in validated_data:
            validated_data['subtotal'] = transaction.total_sale_price
        
        if 'tax_rate' not in validated_data:
            validated_data['tax_rate'] = 0
        
        if 'tax_amount' not in validated_data:
            validated_data['tax_amount'] = validated_data['subtotal'] * (validated_data['tax_rate'] / 100)
        
        if 'total' not in validated_data:
            validated_data['total'] = validated_data['subtotal'] + validated_data['tax_amount']
        
        if 'customer_info' not in validated_data and transaction.customer:
            customer = transaction.customer
            validated_data['customer_info'] = {
                'name': customer.name,
                'email': customer.email,
                'phone': customer.phone,
                'address': customer.address
            }
        
        invoice = Invoice.objects.create(
            transaction_history=transaction,
            **validated_data
        )
        
        return invoice