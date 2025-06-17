from rest_framework import serializers
from .models import Customer
from transactions.models import TransactionHistory, TransactionItem
from django.utils import timezone


class CustomerSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()
    orders_count = serializers.IntegerField(read_only=True, default=0)
    last_purchase_date = serializers.DateField(read_only=True, allow_null=True)
    total_spending = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=0)
    follow_up_display = serializers.SerializerMethodField()
    customer_tags = serializers.CharField(read_only=True)
    # status = serializers.SerializerMethodField()
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'email', 'phone', 'address', 'notes', 
            'status', 'status_display', 'profile_picture',
            'orders_count', 'last_purchase_date', 'total_spending',
            'follow_up_display', 'customer_tags'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_status_display(self, obj):
        return 'Active' if obj.status else 'Inactive'
    
    # def get_follow_up_display(self, obj):
    #     # First check if we have the annotated field
    #     if hasattr(obj, 'follow_up_status'):
    #         status = obj.follow_up_status
    #     else:
    #         # Fallback calculation if annotation isn't present
    #         today = timezone.now().date()
    #         if obj.orders_count == 0:
    #             status = 'yes'
    #         elif obj.last_purchase_date:
    #             days_since = (today - obj.last_purchase_date).days
    #             if days_since > 30:
    #                 status = 'yes'
    #             elif 7 <= days_since <= 30:
    #                 status = 'upcoming'
    #             else:
    #                 status = 'no'
    #         else:
    #             status = 'yes'
        
    #     return {
    #         'yes': 'Yes',
    #         'upcoming': 'Upcoming',
    #         'no': 'No'
    #     }.get(status, 'No')
    
    def get_follow_up_display(self, obj):
        if hasattr(obj, 'follow_up_status'):
            status = obj.follow_up_status
        else:
            today = timezone.now().date()
            
            if not obj.follow_up.due_date:
                status = 'yes'
            elif obj.follow_up.due_date < today:
                status = 'no'
            else:
                status = 'upcoming'
        
        return {
            'yes': 'Yes',
            'upcoming': 'Upcoming', 
            'no': 'No'
        }.get(status, 'No')

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
    
    # def get_status(self, obj):
    #     return getattr(obj, 'is_active_customer', obj.status)


class CustomerCreateSerializer(serializers.ModelSerializer):
    profile_picture=serializers.ImageField(required=False)
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address', 'notes', 'status', 'profile_picture']
    
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

class DashboardMetricsSerializer(serializers.Serializer):
    total_customers = serializers.IntegerField()
    avg_spending = serializers.DecimalField(max_digits=10, decimal_places=2)
    follow_ups_due = serializers.IntegerField()
    new_leads_this_month = serializers.IntegerField()


class TransactionItemSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='product.model_name', read_only=True)
    brand = serializers.CharField(source='product.category.name', read_only=True)
    reference_number = serializers.CharField(source='product.product_id', read_only=True)
    # image_url = serializers.CharField(source='product.image.url', read_only=True)
    total_purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_sale_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    image_url = serializers.SerializerMethodField()
    class Meta:
        model = TransactionItem
        fields = [
            'id',
            'product',
            'reference_number',
            'model_name',
            'brand',
            'image_url',
            'quantity',
            'purchase_price',
            'sale_price',
            'total_purchase_price',
            'total_sale_price'
        ]

    def get_image_url(self, obj):
        if obj.product and obj.product.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.product.image.url) if request else obj.product.image.url
        return None


class CustomerOrderSerializer(serializers.ModelSerializer):
    transaction_items = TransactionItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    total_purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_sale_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    profit = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TransactionHistory
        fields = [
            'id',
            'name_of_trade',
            'transaction_type',
            'date',
            'purchase_price',
            'sale_price',
            'sale_category',
            'customer_name',
            'notes',
            'expenses',
            'total_purchase_price',
            'total_sale_price',
            'profit',
            'items_count',
            'transaction_items',
            'created_at',
            'updated_at'
        ]
    
    def get_items_count(self, obj):
        return obj.transaction_items.count()
    
class CustomerBulkSerializer(serializers.ModelSerializer):
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    last_purchase_date = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'email', 'phone', 'status', 
            'total_spent', 'last_purchase_date', 'tags_list',
            'created_at'
        ]
    
    def get_last_purchase_date(self, obj):
        last_purchase = obj.transactions_customer.filter(
            transaction_type='sale'
        ).order_by('-date').first()
        return last_purchase.date if last_purchase else None
    
    def get_tags_list(self, obj):
        return [{'id': tag.id, 'name': tag.name, 'color': tag.color} for tag in obj.tags.all()]


class BulkActionSerializer(serializers.Serializer):
    BULK_ACTION_CHOICES = [
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('mark_follow_up', 'Mark for Follow-up'),
        ('add_tag', 'Add Tag'),
        ('remove_tag', 'Remove Tag'),
        ('send_newsletter', 'Send Newsletter'),
        ('delete', 'Delete'),
    ]
    
    customer_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100  # Limit bulk operations
    )
    action = serializers.ChoiceField(choices=BULK_ACTION_CHOICES)
    action_data = serializers.JSONField(default=dict, required=False)
    
    def validate_customer_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate customer IDs are not allowed")
        return value
    
    def validate(self, data):
        action = data.get('action')
        action_data = data.get('action_data', {})
        
        # Validate action-specific requirements
        if action == 'mark_follow_up' and not action_data.get('due_date'):
            raise serializers.ValidationError({
                'action_data': 'due_date is required for follow-up action'
            })
        
        if action in ['add_tag', 'remove_tag'] and not action_data.get('tag_id'):
            raise serializers.ValidationError({
                'action_data': 'tag_id is required for tag actions'
            })
        
        if action == 'send_newsletter' and not action_data.get('message'):
            raise serializers.ValidationError({
                'action_data': 'message is required for newsletter action'
            })
        
        return data