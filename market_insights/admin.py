from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Avg, Count, Min, Max
from django.utils import timezone
from datetime import timedelta
from .models import MarketData

class MarketDataAdmin(admin.ModelAdmin):
    list_display = (
        'product_link', 'source_badge', 'reference_number', 'formatted_price', 
        'brand', 'condition_badge', 'name_truncated', 
        'scraped_date', 'listing_date', 'actions_column'
    )
    
    list_display_links = ('formatted_price',)
    
    search_fields = (
        'product__model_name', 'name', 'brand', 'reference_number', 
        'item_id', 'condition'
    )
    
    list_filter = (
        'source', 
        'brand', 
        'condition',
        ('scraped_at', admin.DateFieldListFilter),
        ('listing_date', admin.DateFieldListFilter),
        ('price', admin.SimpleListFilter),
    )
    
    readonly_fields = (
        'scraped_at', 'item_id', 'image_preview', 
        'external_links', 'price_analysis'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('product', 'source', 'name', 'brand', 'reference_number')
        }),
        ('Pricing & Condition', {
            'fields': ('price', 'condition', 'price_analysis')
        }),
        ('External Data', {
            'fields': ('item_id', 'product_url', 'listing_url', 'external_links'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('image_url', 'image_preview'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('scraped_at', 'listing_date'),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ('-scraped_at',)
    list_per_page = 25
    date_hierarchy = 'scraped_at'
    
    actions = ['mark_as_verified', 'update_pricing_data', 'export_selected']
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('product')
    
    def product_link(self, obj):
        """Display product with link to change page"""
        if obj.product:
            url = reverse('admin:inventory_product_change', args=[obj.product.pk])
            return format_html('<a href="{}">{}</a>', url, obj.product)
        return '-'
    product_link.short_description = 'Product'
    product_link.admin_order_field = 'product__model_name'
    
    def source_badge(self, obj):
        """Display source as colored badge"""
        colors = {
            'ebay': '#0064D2',
            'chrono24': '#FF6900', 
            'bezel': '#8B5CF6',
            'grailzee': '#10B981'
        }
        color = colors.get(obj.source, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_source_display()
        )
    source_badge.short_description = 'Source'
    source_badge.admin_order_field = 'source'
    
    def formatted_price(self, obj):
        """Display price with currency formatting"""
        return format_html('<strong>${}</strong>', '{:,.2f}'.format(obj.price))
    formatted_price.short_description = 'Price'
    formatted_price.admin_order_field = 'price'
    
    def condition_badge(self, obj):
        """Display condition as colored badge"""
        if not obj.condition:
            return '-'
        
        colors = {
            'new': '#10B981',
            'excellent': '#059669', 
            'good': '#F59E0B',
            'fair': '#EF4444',
            'poor': '#DC2626'
        }
        color = colors.get(obj.condition.lower(), '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 8px; font-size: 10px;">{}</span>',
            color, obj.condition.title()
        )
    condition_badge.short_description = 'Condition'
    condition_badge.admin_order_field = 'condition'
    
    def name_truncated(self, obj):
        """Display truncated name with tooltip"""
        if not obj.name:
            return '-'
        truncated = obj.name[:50] + '...' if len(obj.name) > 50 else obj.name
        return format_html('<span title="{}">{}</span>', obj.name, truncated)
    name_truncated.short_description = 'Name'
    name_truncated.admin_order_field = 'name'
    
    def scraped_date(self, obj):
        """Display relative scraped date"""
        now = timezone.now()
        diff = now - obj.scraped_at
        
        if diff.days == 0:
            return format_html('<span style="color: #10B981;">Today</span>')
        elif diff.days == 1:
            return format_html('<span style="color: #F59E0B;">Yesterday</span>')
        elif diff.days <= 7:
            return format_html('<span style="color: #EF4444;">{} days ago</span>', str(diff.days))
        else:
            return obj.scraped_at.strftime('%m/%d/%Y')
    scraped_date.short_description = 'Scraped'
    scraped_date.admin_order_field = 'scraped_at'
    
    def actions_column(self, obj):
        """Display action buttons"""
        buttons = []
        
        if obj.listing_url:
            buttons.append(
                '<a href="{}" target="_blank" style="margin-right: 5px;" '
                'title="View Listing">📋</a>'.format(obj.listing_url)
            )
        
        if obj.product_url:
            buttons.append(
                '<a href="{}" target="_blank" style="margin-right: 5px;" '
                'title="View Product">🔗</a>'.format(obj.product_url)
            )
            
        if obj.image_url:
            buttons.append(
                '<a href="{}" target="_blank" title="View Image">🖼️</a>'.format(obj.image_url)
            )
        
        return format_html(''.join(buttons))
    actions_column.short_description = 'Actions'
    
    def image_preview(self, obj):
        """Display image preview in admin"""
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; '
                'border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.image_url
            )
        return 'No image available'
    image_preview.short_description = 'Image Preview'
    
    def external_links(self, obj):
        """Display external links"""
        links = []
        if obj.listing_url:
            links.append(f'<a href="{obj.listing_url}" target="_blank">View Listing</a>')
        if obj.product_url:
            links.append(f'<a href="{obj.product_url}" target="_blank">View Product Page</a>')
        
        return format_html('<br>'.join(links)) if links else 'No external links'
    external_links.short_description = 'External Links'
    
    def price_analysis(self, obj):
        """Display price analysis for the product"""
        if not obj.product:
            return 'No product associated'
        
        # Get price statistics for this product
        market_data = MarketData.objects.filter(product=obj.product)
        stats = market_data.aggregate(
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
            count=Count('id')
        )
        
        current_price = obj.price
        avg_price = stats['avg_price'] or 0
        
        if avg_price > 0:
            price_diff = ((current_price - avg_price) / avg_price) * 100
            color = '#10B981' if price_diff < 0 else '#EF4444'
            arrow = '↓' if price_diff < 0 else '↑'
            
            analysis = format_html(
                '<div style="font-size: 12px;">'
                '<strong>Current:</strong> ${}<br>'
                '<strong>Average:</strong> ${}<br>'
                '<strong>Range:</strong> ${} - ${}<br>'
                '<span style="color: {}; font-weight: bold;">'
                '{} {:+.1f}% vs avg</span><br>'
                '<small>Based on {} listings</small>'
                '</div>',
                '{:,.2f}'.format(current_price),
                '{:,.2f}'.format(avg_price),
                '{:,.2f}'.format(stats['min_price'] or 0),
                '{:,.2f}'.format(stats['max_price'] or 0),
                color,
                arrow,
                price_diff,
                stats['count']
            )
            return analysis
        
        return 'Insufficient data for analysis'
    price_analysis.short_description = 'Price Analysis'
    
    # Custom Actions
    def mark_as_verified(self, request, queryset):
        """Custom action to mark selected items as verified"""
        count = queryset.count()
        # Add your verification logic here
        self.message_user(request, '{} market data entries marked as verified.'.format(count))
    mark_as_verified.short_description = 'Mark selected items as verified'
    
    def update_pricing_data(self, request, queryset):
        """Custom action to trigger price updates"""
        count = queryset.count()
        # Add your update logic here
        self.message_user(request, 'Triggered price updates for {} items.'.format(count))
    update_pricing_data.short_description = 'Update pricing data'
    
    def export_selected(self, request, queryset):
        """Custom action to export selected data"""
        count = queryset.count()
        # Add your export logic here
        self.message_user(request, 'Exported {} market data entries.'.format(count))
    export_selected.short_description = 'Export selected data'

# Custom list filter for price ranges
class PriceRangeFilter(admin.SimpleListFilter):
    title = 'price range'
    parameter_name = 'price_range'
    
    def lookups(self, request, model_admin):
        return (
            ('0-100', '$0 - $100'),
            ('100-500', '$100 - $500'),
            ('500-1000', '$500 - $1,000'),
            ('1000-5000', '$1,000 - $5,000'),
            ('5000+', '$5,000+'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == '0-100':
            return queryset.filter(price__lt=100)
        elif self.value() == '100-500':
            return queryset.filter(price__gte=100, price__lt=500)
        elif self.value() == '500-1000':
            return queryset.filter(price__gte=500, price__lt=1000)
        elif self.value() == '1000-5000':
            return queryset.filter(price__gte=1000, price__lt=5000)
        elif self.value() == '5000+':
            return queryset.filter(price__gte=5000)

# Update the list_filter to use the custom filter
MarketDataAdmin.list_filter = (
    'source', 
    'brand', 
    'condition',
    ('scraped_at', admin.DateFieldListFilter),
    ('listing_date', admin.DateFieldListFilter),
    PriceRangeFilter,
)

admin.site.register(MarketData, MarketDataAdmin)