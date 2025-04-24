from rest_framework import serializers
from .models import Shipment

class ShipmentSerializer(serializers.ModelSerializer):
    transaction_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Shipment
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_transaction_details(self, obj):
        return {
            'id': obj.transaction.id,
            'watch': str(obj.transaction.product)
        }

class ShippingCalculatorSerializer(serializers.Serializer):
    origin_zip = serializers.CharField()
    destination_zip = serializers.CharField()
    weight = serializers.FloatField()
    package_type = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)