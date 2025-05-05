# serializers.py
from rest_framework import serializers
from .models import MarketData

class MarketDataSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = MarketData
        fields = '__all__'
