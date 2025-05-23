from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ShippingConfig, SenderAddress, RecipientAddress, 
    Shipment, NotificationEmail, ShipmentProduct
)


@admin.register(ShippingConfig)
class ShippingConfigAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_id', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'account_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('IFS Configuration', {
            'fields': ('app_username', 'app_password', 'account_id')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent adding multiple configs for the same user
        return super().has_add_permission(request)


@admin.register(SenderAddress)
class SenderAddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_name', 'city', 'state', 'zip_code', 'is_primary', 'is_residential']
    list_filter = ['is_primary', 'is_residential', 'state', 'country']
    search_fields = ['name', 'company_name', 'address1', 'city', 'email', 'ifs_id']
    list_editable = ['is_primary']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('ifs_id', 'name', 'company_name', 'phone', 'email')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'zip_code', 'country')
        }),
        ('Options', {
            'fields': ('is_residential', 'is_primary')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(RecipientAddress)
class RecipientAddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_name', 'city', 'state', 'zip_code', 'is_verified', 'is_residential']
    list_filter = ['is_verified', 'is_residential', 'state', 'country']
    search_fields = ['name', 'company_name', 'label_name', 'address1', 'city', 'email', 'ifs_id']
    list_editable = ['is_verified']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('ifs_id', 'name', 'company_name', 'label_name', 'phone', 'email')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'zip_code', 'country')
        }),
        ('Options', {
            'fields': ('is_residential', 'is_verified')
        }),
    )


class NotificationEmailInline(admin.TabularInline):
    model = NotificationEmail
    extra = 1
    fields = ['name', 'email', 'message']


class ShipmentProductInline(admin.TabularInline):
    model = ShipmentProduct
    extra = 1
    fields = ['name', 'description', 'quantity', 'gross_weight', 'weight_unit', 'value', 'origin_country']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_history', 'tracking_number', 'status', 'service_type', 
        'shipping_cost', 'shipped_date', 'estimated_delivery'
    ]
    list_filter = [
        'status', 'service_type', 'package_type', 'payment_type', 
        'is_international', 'saturday_delivery', 'shipped_date'
    ]
    search_fields = [
        'tracking_number', 'ifs_shipment_id', 'reference', 
        'sender__name', 'recipient__name', 'transaction_history__product'
    ]
    list_editable = ['status']
    readonly_fields = [
        'created_at', 'updated_at', 'tracking_link', 'label_links', 
        'shipment_summary'
    ]
    
    inlines = [NotificationEmailInline, ShipmentProductInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'transaction_history', 'sender', 'recipient', 'status', 
                'reference', 'reference_on_label'
            )
        }),
        ('IFS Information', {
            'fields': ('ifs_shipment_id', 'tracking_number', 'zone_id'),
            'classes': ('collapse',)
        }),
        ('Package Details', {
            'fields': (
                'package_type', 'service_type', 'package_weight',
                'package_length', 'package_width', 'package_height',
                'declared_value'
            )
        }),
        ('Shipment Options', {
            'fields': (
                'payment_type', 'account_number', 'signature_type',
                'saturday_delivery', 'hold_at_location'
            )
        }),
        ('Hold at Location Details', {
            'fields': (
                'hal_contact_person', 'hal_company_name', 'hal_address',
                'hal_city', 'hal_state', 'hal_zip_code', 'hal_phone',
                'hal_location_property'
            ),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': (
                'pickup_date', 'estimated_delivery', 'shipped_date', 
                'delivered_date'
            )
        }),
        ('Labels & Documents', {
            'fields': (
                'label_format', 'label_url', 'commercial_invoice_url',
                'return_label_url', 'receipt_url'
            )
        }),
        ('International Shipping', {
            'fields': (
                'is_international', 'duties_taxes_paid_by', 'customs_value'
            ),
            'classes': ('collapse',)
        }),
        ('Cost & Tracking', {
            'fields': ('shipping_cost', 'tracking_history')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'shipment_summary'),
            'classes': ('collapse',)
        }),
    )
    
    def tracking_link(self, obj):
        if obj.tracking_number:
            # FedEx tracking URL
            url = f"https://www.fedex.com/apps/fedextrack/?tracknumbers={obj.tracking_number}"
            return format_html(
                '<a href="{}" target="_blank">Track Package: {}</a>',
                url, obj.tracking_number
            )
        return "No tracking number"
    tracking_link.short_description = "Tracking Link"
    
    def label_links(self, obj):
        links = []
        if obj.label_url:
            links.append(f'<a href="{obj.label_url}" target="_blank">Shipping Label</a>')
        if obj.commercial_invoice_url:
            links.append(f'<a href="{obj.commercial_invoice_url}" target="_blank">Commercial Invoice</a>')
        if obj.return_label_url:
            links.append(f'<a href="{obj.return_label_url}" target="_blank">Return Label</a>')
        if obj.receipt_url:
            links.append(f'<a href="{obj.receipt_url}" target="_blank">Receipt</a>')
        
        return mark_safe('<br>'.join(links)) if links else "No labels available"
    label_links.short_description = "Document Links"
    
    def shipment_summary(self, obj):
        summary = f"""
        <strong>From:</strong> {obj.sender.name}<br>
        <strong>To:</strong> {obj.recipient.name}<br>
        <strong>Service:</strong> {obj.get_service_type_display()}<br>
        <strong>Package:</strong> {obj.get_package_type_display()}<br>
        <strong>Weight:</strong> {obj.package_weight} lbs<br>
        <strong>Cost:</strong> ${obj.shipping_cost}
        """
        return mark_safe(summary)
    shipment_summary.short_description = "Shipment Summary"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'transaction_history', 'sender', 'recipient'
        )
    
    # Custom actions
    actions = ['mark_as_shipped', 'mark_as_delivered', 'void_shipment']
    
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='in_transit', shipped_date=timezone.now().date())
        self.message_user(request, f'{updated} shipments marked as shipped.')
    mark_as_shipped.short_description = "Mark selected shipments as shipped"
    
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='delivered', delivered_date=timezone.now().date())
        self.message_user(request, f'{updated} shipments marked as delivered.')
    mark_as_delivered.short_description = "Mark selected shipments as delivered"
    
    def void_shipment(self, request, queryset):
        updated = queryset.update(status='voided')
        self.message_user(request, f'{updated} shipments voided.')
    void_shipment.short_description = "Void selected shipments"


@admin.register(NotificationEmail)
class NotificationEmailAdmin(admin.ModelAdmin):
    list_display = ['shipment', 'name', 'email', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'email', 'shipment__tracking_number']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shipment')


@admin.register(ShipmentProduct)
class ShipmentProductAdmin(admin.ModelAdmin):
    list_display = [
        'shipment', 'name', 'quantity', 'gross_weight', 
        'weight_unit', 'value', 'origin_country'
    ]
    list_filter = ['weight_unit', 'origin_country', 'created_at']
    search_fields = [
        'name', 'description', 'hts_number', 
        'shipment__tracking_number'
    ]
    
    fieldsets = (
        ('Product Information', {
            'fields': ('shipment', 'name', 'description', 'hts_number')
        }),
        ('Physical Properties', {
            'fields': ('quantity', 'gross_weight', 'weight_unit')
        }),
        ('Value & Origin', {
            'fields': ('value', 'origin_country')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shipment')


# Custom admin site configuration
admin.site.site_header = "Shipping Management System"
admin.site.site_title = "Shipping Admin"
admin.site.index_title = "Shipping Administration"