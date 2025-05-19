from rest_framework import serializers
from .models import Customer

class CustomerSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()
    orders_count = serializers.IntegerField(read_only=True, default=0)
    last_purchase_date = serializers.DateField(read_only=True, allow_null=True)
    total_spending = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=0)
    follow_up_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'email', 'phone', 'address', 'notes', 
            'status', 'status_display', 'profile_picture',
            'orders_count', 'last_purchase_date', 'total_spending',
            'follow_up_display'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_status_display(self, obj):
        return 'Active' if obj.status else 'Inactive'
    
    def get_follow_up_display(self, obj):
        if hasattr(obj, 'follow_up'):
            return 'Yes' if obj.follow_up else 'No'
        return 'No'
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        if data['phone']:
            phone = data['phone'].replace('-', '').replace(' ', '')
            if len(phone) == 10:
                data['phone'] = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        
        return data
        
    def validate_email(self, value):
        if not value:
            return value
            
        user = self.context['request'].user
        existing = Customer.objects.filter(user=user, email=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        
        if existing.exists():
            raise serializers.ValidationError("You already have a customer with this email address.")
        return value


class CustomerCreateSerializer(serializers.ModelSerializer):
    profile_picture=serializers.ImageField(required=False)
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address', 'notes', 'status']
    
    def validate_email(self, value):
        if not value:
            return value
            
        user = self.context['request'].user
        if Customer.objects.filter(user=user, email=value).exists():
            raise serializers.ValidationError("You already have a customer with this email address.")
        return value
    

class CustomerDetailSerializer(CustomerSerializer):
    last_transaction_details = serializers.SerializerMethodField()
    related_invoices = serializers.SerializerMethodField()
    
    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + [
            'last_transaction_details', 'related_invoices'
        ]
    
    def get_last_transaction_details(self, obj):
        try:
            transaction = obj.transactions_customer.order_by('-date').first()
            if transaction:
                return {
                    'id': transaction.id,
                    'date': transaction.date,
                    'transaction_type': transaction.transaction_type,
                    'amount': transaction.sale_price or 0,
                    'name': transaction.name_of_trade
                }
        except:
            pass
        return None
    
    def get_related_invoices(self, obj):
        invoices = []
        try:
            for transaction in obj.transactions_customer.all():
                if hasattr(transaction, 'invoice'):
                    invoices.append({
                        'id': transaction.invoice.id,
                        'invoice_number': transaction.invoice.invoice_number,
                        'status': transaction.invoice.status,
                        'total': str(transaction.invoice.total),
                        'due_date': transaction.invoice.due_date,
                        'issue_date': transaction.invoice.issue_date
                    })
        except:
            pass
        return invoices
