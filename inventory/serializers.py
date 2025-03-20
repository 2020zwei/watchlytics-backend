from rest_framework import serializers
from .models import Brand, WatchModel, Watch

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class WatchModelSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='brand.name')
    
    class Meta:
        model = WatchModel
        fields = '__all__'

class WatchSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='watch_model.brand.name')
    model_name = serializers.ReadOnlyField(source='watch_model.name')
    days_in_inventory = serializers.ReadOnlyField()
    stock_age_category = serializers.ReadOnlyField()
    
    class Meta:
        model = Watch
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')