from django.contrib import admin
from .models import MarketData

class MarketDataAdmin(admin.ModelAdmin):
    list_display = ('product', 'source', 'price', 'item_id', 'name', 'scraped_at', 'listing_date', 'brand', 'condition')
    search_fields = ('product__name', 'source', 'item_id', 'name', 'brand', 'condition')
    list_filter = ('source', 'brand', 'condition', 'scraped_at', 'listing_date')
    ordering = ('-scraped_at',)

admin.site.register(MarketData, MarketDataAdmin)
