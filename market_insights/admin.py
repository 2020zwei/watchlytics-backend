from django.contrib import admin
from .models import MarketData

@admin.register(MarketData)
class MarketDataAdmin(admin.ModelAdmin):
    list_display = ('product', 'source', 'price', 'listing_date', 'scraped_at')
    list_filter = ('source', 'listing_date', 'product')
    # search_fields = ('product_name', 'product_id')
    fieldsets = (
        ('Watch Information', {
            'fields': ('product',)
        }),
        ('Market Data', {
            'fields': ('source', 'price', 'condition', 'listing_date', 'listing_url')
        }),
        ('Additional Information', {
            'fields': ('additional_info',),
            'classes': ('collapse',)
        }),
    )