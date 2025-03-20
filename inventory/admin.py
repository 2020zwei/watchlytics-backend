from django.contrib import admin
from .models import Brand, WatchModel, Watch

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(WatchModel)
class WatchModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'reference_number')
    list_filter = ('brand',)
    search_fields = ('name', 'reference_number', 'brand__name')

@admin.register(Watch)
class WatchAdmin(admin.ModelAdmin):
    list_display = ('watch_model', 'serial_number', 'condition', 'status', 'purchase_price', 
                   'asking_price', 'purchase_date', 'days_in_inventory', 'stock_age_category')
    list_filter = ('status', 'condition', 'watch_model__brand')
    search_fields = ('serial_number', 'watch_model__name', 'watch_model__brand__name')
    readonly_fields = ('days_in_inventory', 'stock_age_category')
    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'watch_model', 'serial_number', 'year', 'status')
        }),
        ('Condition & Details', {
            'fields': ('condition', 'box', 'papers', 'certificate', 'description')
        }),
        ('Purchase Information', {
            'fields': ('purchase_price', 'purchase_date', 'purchase_notes')
        }),
        ('Sales Information', {
            'fields': ('asking_price',)
        }),
        ('Media', {
            'fields': ('images',)
        }),
        ('Additional Information', {
            'fields': ('additional_info',)
        }),
        ('Inventory Metrics', {
            'fields': ('days_in_inventory', 'stock_age_category'),
            'classes': ('collapse',)
        }),
    )
