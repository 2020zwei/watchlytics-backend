from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Avg, Count
from django.urls import reverse
from .models import Product, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'product_count')
    search_fields = ('name', 'description')
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Number of Products"

class ProductStockAgeListFilter(admin.SimpleListFilter):
    title = 'Stock Age'
    parameter_name = 'stock_age'
    
    def lookups(self, request, model_admin):
        return (
            ('less_than_30', 'Less than 30 days'),
            ('30_to_60', '30 to 60 days'),
            ('60_to_90', '60 to 90 days'),
            ('more_than_90', 'More than 90 days'),
        )
    
    def queryset(self, request, queryset):
        return queryset  # This would need custom implementation based on your stock_age_category property

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name', 'owner_display', 'category', 'buying_price', 
                   'sold_price', 'profit_display', 'quantity', 'date_purchased', 
                   'date_sold', 'is_sold_display', 'days_in_inventory_display')
    
    list_filter = ('category', 'availability', ProductStockAgeListFilter, 'owner')
    search_fields = ('product_name', 'product_id', 'owner__username', 'purchased_from', 'sold_source')
    readonly_fields = ('created_at', 'updated_at', 'calculated_profit', 'days_in_inventory')
    date_hierarchy = 'date_purchased'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'product_name', 'product_id', 'category', 'availability', 'quantity', 'unit')
        }),
        ('Financial Information', {
            'fields': ('buying_price', 'shipping_price', 'repair_cost', 'fees', 'commission', 
                      'msrp', 'sold_price', 'whole_price', 'website_price', 'profit_margin', 'calculated_profit')
        }),
        ('Dates', {
            'fields': ('date_purchased', 'purchase_date', 'date_sold', 'hold_time', 'days_in_inventory')
        }),
        ('Source Information', {
            'fields': ('purchased_from', 'source_of_sale', 'sold_source', 'listed_on')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def owner_display(self, obj):
        if obj.owner:
            return format_html('<a href="{}">{}</a>', 
                              reverse('admin:auth__user_change', args=(obj.owner.pk,)),
                              obj.owner.username)
        return "-"
    owner_display.short_description = "Owner"
    
    def is_sold_display(self, obj):
        return format_html('<span style="color: {};">{}</span>', 
                          'green' if obj.is_sold else 'red', 
                          'Yes' if obj.is_sold else 'No')
    is_sold_display.short_description = "Sold"
    
    def profit_display(self, obj):
        try:
            profit = float(obj.calculated_profit)
        except (TypeError, ValueError):
            profit = 0.0
        color = "green" if profit >= 0 else "red"
        return format_html('<span style="color: {};">${}</span>', color, '{:.2f}'.format(profit))
    profit_display.short_description = "Profit"
    
    def days_in_inventory_display(self, obj):
        days = obj.days_in_inventory
        if days is None:
            return "-"
        
        # Color code based on age
        if days < 30:
            color = 'green'
        elif days < 60:
            color = 'orange'
        elif days < 90:
            color = 'darkorange'
        else:
            color = 'red'
            
        return format_html('<span style="color: {};">{} days</span>', color, days)
    days_in_inventory_display.short_description = "Days in Inventory"
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('owner', 'category')