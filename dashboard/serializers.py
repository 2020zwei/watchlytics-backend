from rest_framework import serializers
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from transactions.models import TransactionHistory, TransactionItem
from inventory.models import Product


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    manage_in_stock = serializers.IntegerField()
    sold_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_sale = serializers.IntegerField()
    total_orders = serializers.IntegerField()


class ExpenseTrackingSerializer(serializers.Serializer):
    """Serializer for expense tracking chart data"""
    month = serializers.CharField()
    sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    purchases = serializers.DecimalField(max_digits=12, decimal_places=2)


class IncomeBreakdownSerializer(serializers.Serializer):
    """Serializer for income breakdown pie chart"""
    target = serializers.DecimalField(max_digits=12, decimal_places=2)
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending = serializers.DecimalField(max_digits=12, decimal_places=2)