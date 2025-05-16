from rest_framework import serializers
from .models import Customer

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'phone' , 'address', 'status']
        read_only_fields = ['id', 'name', 'email', 'phone' , 'address']
