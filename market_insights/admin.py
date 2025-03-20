from django.contrib import admin
from .models import MarketData

@admin.register(MarketData)
class MarketDataAdmin(admin.ModelAdmin):
    list_display = ('watch_model', 'source', 'price', 'listing_date', 'scraped_at')
    list_filter = ('source', 'listing_date', 'watch_model__brand')
    search_fields = ('watch_model__name', 'watch_model__brand__name')
    fieldsets = (
        ('Watch Information', {
            'fields': ('watch_model',)
        }),
        ('Market Data', {
            'fields': ('source', 'price', 'condition', 'listing_date', 'listing_url')
        }),
        ('Additional Information', {
            'fields': ('additional_info',),
            'classes': ('collapse',)
        }),
    )