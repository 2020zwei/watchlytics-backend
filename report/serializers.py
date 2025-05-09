from rest_framework import serializers
from inventory.models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    days_in_inventory = serializers.ReadOnlyField()
    calculated_profit = serializers.ReadOnlyField()
    stock_age_category = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'product_id', 'product_name', 'category', 'category_name', 
            'availability', 'buying_price', 'shipping_price', 'repair_cost',
            'fees', 'commission', 'msrp', 'sold_price', 'whole_price', 
            'website_price', 'profit_margin', 'profit', 'quantity', 'unit',
            'date_purchased', 'purchase_date', 'date_sold', 'hold_time',
            'source_of_sale', 'delivery_content', 'condition', 
            'purchased_from', 'sold_source', 'listed_on', 'image',
            'days_in_inventory', 'calculated_profit', 'stock_age_category',
            'owner', 'serial_number'
        ]


class DashboardStatsSerializer(serializers.Serializer):
    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    sales = serializers.IntegerField()
    net_purchase_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_sales_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    mom_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    yoy_profit = serializers.DecimalField(max_digits=12, decimal_places=2)


class BestSellingProductSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    product_id = serializers.CharField()
    category_name = serializers.CharField()
    quantity = serializers.IntegerField()
    remaining_quantity = serializers.IntegerField()
    turn_over = serializers.DecimalField(max_digits=12, decimal_places=2)
    increase_by = serializers.DecimalField(max_digits=6, decimal_places=2)


class RepairCostSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    cost = serializers.DecimalField(max_digits=12, decimal_places=2)


class StockAgingSerializer(serializers.Serializer):
    age_category = serializers.CharField()
    count = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=12, decimal_places=2)


class ExpenseReportSerializer(serializers.Serializer):
    buying_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    repair_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    fees = serializers.DecimalField(max_digits=12, decimal_places=2)
    commission = serializers.DecimalField(max_digits=12, decimal_places=2)


class MarketComparisonSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    msrp = serializers.DecimalField(max_digits=12, decimal_places=2)
    sold_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    difference = serializers.DecimalField(max_digits=12, decimal_places=2)
    difference_percent = serializers.DecimalField(max_digits=8, decimal_places=2)


class MonthlyProfitSerializer(serializers.Serializer):
    month = serializers.CharField()
    profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    cost = serializers.DecimalField(max_digits=12, decimal_places=2)


class UserReportSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    total_sold = serializers.IntegerField()
    sell_through_rate = serializers.DecimalField(max_digits=6, decimal_places=2)
    avg_profit_margin = serializers.DecimalField(max_digits=6, decimal_places=2)
    avg_days_to_sell = serializers.DecimalField(max_digits=6, decimal_places=2)


class StockTurnoverSerializer(serializers.Serializer):
    category = serializers.CharField()
    sold_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    inventory_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    turnover_ratio = serializers.DecimalField(max_digits=6, decimal_places=2)


class InventorySummarySerializer(serializers.Serializer):
    total_items = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    categories = serializers.ListField(child=serializers.DictField())


class PurchaseSalesReportSerializer(serializers.Serializer):
    period = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    purchases = serializers.ListField(child=serializers.DictField())
    sales = serializers.ListField(child=serializers.DictField())