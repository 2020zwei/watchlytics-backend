
from rest_framework import serializers
from .models import Plan, Subscription, UserCard

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']

class UserCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCard
        fields = ['id', 'card_brand', 'last_four', 'card_holder_name' , 'exp_month', 'exp_year', 'is_default', 'stripe_payment_method_id',  'created_at']
        read_only_fields = ['id', 'card_brand', 'last_four', 'exp_month', 'exp_year', 'stripe_payment_method_id', 'created_at']