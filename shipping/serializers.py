from rest_framework import serializers
from .models import (
    Shipment, 
    SenderAddress, 
    RecipientAddress, 
    NotificationEmail, 
    ShipmentProduct
)

class SenderAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SenderAddress
        fields = [
            'id', 'ifs_id', 'name', 'company_name', 'address1', 
            'address2', 'city', 'state', 'zip_code', 'country', 
            'phone', 'email', 'is_residential', 'is_primary'
        ]
        read_only_fields = ['ifs_id', 'created_at', 'updated_at']


class RecipientAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipientAddress
        fields = [
            'id', 'ifs_id', 'name', 'company_name', 'label_name',
            'address1', 'address2', 'city', 'state', 'zip_code', 
            'country', 'phone', 'email', 'is_residential', 'is_verified'
        ]
        read_only_fields = ['ifs_id', 'is_verified', 'created_at', 'updated_at']


class NotificationEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEmail
        fields = ['id', 'name', 'email', 'message']


class ShipmentProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentProduct
        fields = [
            'id', 'name', 'description', 'hts_number', 'weight_unit',
            'quantity', 'gross_weight', 'value', 'origin_country'
        ]


class ShipmentCreateSerializer(serializers.ModelSerializer):
    notification_emails = NotificationEmailSerializer(many=True, required=False)
    products = ShipmentProductSerializer(many=True, required=False)
    
    class Meta:
        model = Shipment
        fields = [
            'transaction_history', 'sender', 'recipient',
            'package_type', 'service_type', 'package_weight',
            'package_length', 'package_width', 'package_height',
            'declared_value', 'payment_type', 'account_number',
            'signature_type', 'saturday_delivery', 'hold_at_location',
            'hal_contact_person', 'hal_company_name', 'hal_address',
            'hal_city', 'hal_state', 'hal_zip_code', 'hal_phone',
            'pickup_date', 'label_format', 'reference', 'reference_on_label',
            'notification_emails', 'products', 'is_international',
            'duties_taxes_paid_by', 'customs_value'
        ]
    
    def create(self, validated_data):
        # Extract nested data
        notification_emails_data = validated_data.pop('notification_emails', [])
        products_data = validated_data.pop('products', [])
        
        # Create shipment
        shipment = Shipment.objects.create(**validated_data)
        
        # Create notification emails
        for email_data in notification_emails_data:
            NotificationEmail.objects.create(shipment=shipment, **email_data)
        
        # Create products for international shipments
        for product_data in products_data:
            ShipmentProduct.objects.create(shipment=shipment, **product_data)
            
        return shipment


class ShipmentDetailSerializer(serializers.ModelSerializer):
    sender = SenderAddressSerializer(read_only=True)
    recipient = RecipientAddressSerializer(read_only=True)
    notification_emails = NotificationEmailSerializer(many=True, read_only=True)
    products = ShipmentProductSerializer(many=True, read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'transaction_history', 'sender', 'recipient',
            'ifs_shipment_id', 'tracking_number', 'zone_id',
            'package_type', 'service_type', 'package_weight',
            'package_length', 'package_width', 'package_height',
            'declared_value', 'payment_type', 'account_number',
            'signature_type', 'saturday_delivery', 'hold_at_location',
            'hal_contact_person', 'hal_company_name', 'hal_address',
            'hal_city', 'hal_state', 'hal_zip_code', 'hal_phone',
            'pickup_date', 'estimated_delivery', 'shipped_date',
            'delivered_date', 'label_format', 'label_url',
            'commercial_invoice_url', 'return_label_url', 'receipt_url',
            'status', 'shipping_cost', 'reference', 'reference_on_label',
            'tracking_history', 'created_at', 'updated_at',
            'notification_emails', 'products', 'is_international',
            'duties_taxes_paid_by', 'customs_value'
        ]
        read_only_fields = [
            'id', 'ifs_shipment_id', 'tracking_number', 'zone_id',
            'estimated_delivery', 'shipped_date', 'delivered_date',
            'label_url', 'commercial_invoice_url', 'return_label_url', 'receipt_url',
            'status', 'shipping_cost', 'tracking_history', 'created_at', 'updated_at'
        ]


class VerifyAddressSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField(required=False)
    client_company_name = serializers.CharField(required=False, allow_blank=True)
    client_address1 = serializers.CharField(required=True)
    client_address2 = serializers.CharField(required=False, allow_blank=True)
    client_city = serializers.CharField(required=True)
    client_state = serializers.CharField(required=True)
    client_country = serializers.CharField(required=True)
    client_zip = serializers.CharField(required=True)


class ShippingCostCalculationSerializer(serializers.Serializer):
    sender_id = serializers.IntegerField()
    recipient_id = serializers.IntegerField()
    package_type = serializers.ChoiceField(choices=Shipment.PACKAGE_TYPE_CHOICES)
    service_type = serializers.ChoiceField(choices=Shipment.SERVICE_TYPE_CHOICES)
    package_weight = serializers.DecimalField(max_digits=8, decimal_places=2)
    package_length = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    package_width = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    package_height = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    declared_value = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    pickup_date = serializers.DateField()
    payment_type = serializers.ChoiceField(choices=Shipment.PAYMENT_TYPE_CHOICES, default='SENDER')
    account_number = serializers.CharField(required=False, allow_blank=True)
    signature_type = serializers.ChoiceField(choices=Shipment.SIGNATURE_TYPE_CHOICES, default='NO_SIGNATURE_REQUIRED')
    residential = serializers.BooleanField(default=False)
    saturday_delivery = serializers.BooleanField(default=False)
    hold_at_location = serializers.BooleanField(default=False)
    # Optional HAL fields
    hal_data = serializers.JSONField(required=False)
    # International fields
    is_international = serializers.BooleanField(default=False)
    duties_taxes_paid_by = serializers.CharField(required=False, allow_blank=True)
    products = serializers.ListField(child=serializers.JSONField(), required=False)