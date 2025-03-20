from django.contrib import admin
from .models import Shipment

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'tracking_number', 'carrier', 'status', 'shipped_date', 'estimated_delivery')
    list_filter = ('status', 'carrier', 'shipped_date')
    search_fields = ('tracking_number', 'transaction__watch__serial_number')
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction',)
        }),
        ('Shipping Details', {
            'fields': ('carrier', 'shipping_method', 'status', 'shipping_cost')
        }),
        ('Tracking Information', {
            'fields': ('tracking_number', 'label_url')
        }),
        ('Dates', {
            'fields': ('shipped_date', 'estimated_delivery', 'delivered_date')
        }),
        ('Address', {
            'fields': ('shipping_address',),
            'classes': ('collapse',)
        }),
        ('Tracking History', {
            'fields': ('tracking_history',),
            'classes': ('collapse',)
        }),
    )