from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.urls import path
from .models import (
    ShippingConfig, SenderAddress, RecipientAddress, 
    Shipment, NotificationEmail, ShipmentProduct
)
from .services.ifs_api_service import IFSAPIService


@admin.register(ShippingConfig)
class ShippingConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'account_id', 'app_username', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'account_id')
    raw_id_fields = ('user',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('IFS API Credentials', {
            'fields': ('app_username', 'app_password', 'account_id'),
            'description': 'IFS API authentication credentials. AppUserName and AppPassword are typically provided by IFS.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:config_id>/test-connection/',
                self.admin_site.admin_view(self.test_connection_view),
                name='shipping_config_test_connection',
            ),
        ]
        return custom_urls + urls
    
    def test_connection_view(self, request, config_id):
        """Test IFS API connection"""
        try:
            config = ShippingConfig.objects.get(pk=config_id)
            
            # Create temporary IFS service with this config
            ifs_service = IFSAPIService()
            ifs_service._config = config  # Override config for testing
            
            # Test basic API call
            result = ifs_service.get_basic_data()
            
            if result.get('status') == 1:  # IFS API returns 1 for success
                messages.success(request, f"Connection successful! Connected to IFS API for account {config.account_id}")
            else:
                messages.error(request, f"Connection failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            messages.error(request, f"Connection test failed: {str(e)}")
        
        return HttpResponseRedirect(reverse('admin:shipping_shippingconfig_change', args=[config_id]))
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        
        # Make app_password readonly in change view for security
        if obj:  # Editing existing object
            readonly_fields.append('app_password')
        
        return readonly_fields
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            # Deactivate other configs for this user if this one is set as active
            if obj.is_active:
                ShippingConfig.objects.filter(user=obj.user, is_active=True).update(is_active=False)
        else:  # Updating existing object
            if obj.is_active:
                # Ensure only one active config per user
                ShippingConfig.objects.exclude(pk=obj.pk).filter(user=obj.user, is_active=True).update(is_active=False)
        
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion if it's the only active config for the user
        if obj and obj.is_active:
            active_configs = ShippingConfig.objects.filter(user=obj.user, is_active=True).count()
            return active_configs > 1
        return True
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for fields
        if 'app_username' in form.base_fields:
            form.base_fields['app_username'].help_text = "Username provided by IFS (typically 'Multi_onDemand')"
        if 'app_password' in form.base_fields:
            form.base_fields['app_password'].help_text = "Password provided by IFS"
        if 'account_id' in form.base_fields:
            form.base_fields['account_id'].help_text = "Your IFS account ID (e.g., '11103')"
        
        return form
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_test_connection'] = True
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(SenderAddress)
class SenderAddressAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_name', 'city', 'state', 'is_primary', 'is_residential', 'created_at')
    list_filter = ('is_primary', 'is_residential', 'state', 'country', 'created_at')
    search_fields = ('name', 'company_name', 'address1', 'city', 'email', 'phone', 'ifs_id')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_primary',)
    actions = ['sync_from_ifs']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('ifs_id', 'name', 'company_name')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'zip_code', 'country')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email')
        }),
        ('Options', {
            'fields': ('is_residential', 'is_primary')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def sync_from_ifs(self, request, queryset):
        """Sync sender addresses from IFS"""
        try:
            ifs_service = IFSAPIService()
            result = ifs_service.get_client_address_list()
            
            synced_count = 0
            for address_data in result.get('client_address', []):
                # Get detailed address data
                detail_result = ifs_service.get_client_address_data(address_data['id'])
                address_detail = detail_result.get('client_address_data', {})
                
                # Update or create sender address
                sender, created = SenderAddress.objects.update_or_create(
                    ifs_id=address_data['id'],
                    defaults={
                        'name': address_detail.get('name', ''),
                        'company_name': address_detail.get('company_name', ''),
                        'address1': address_detail.get('address1', ''),
                        'address2': address_detail.get('address2', ''),
                        'city': address_detail.get('city', ''),
                        'state': address_detail.get('state', ''),
                        'zip_code': address_detail.get('zip', ''),
                        'country': address_detail.get('country', 'United States'),
                        'phone': address_detail.get('phone', ''),
                        'email': address_detail.get('email', ''),
                        'is_residential': address_detail.get('is_residential') == 1,
                        'is_primary': address_data.get('is_primaric') == 1,
                    }
                )
                synced_count += 1
            
            self.message_user(request, f"Successfully synced {synced_count} sender addresses from IFS")
            
        except Exception as e:
            self.message_user(request, f"Error syncing from IFS: {str(e)}", level=messages.ERROR)
    
    sync_from_ifs.short_description = "Sync selected addresses from IFS"
    
    def save_model(self, request, obj, form, change):
        # Ensure only one primary address
        if obj.is_primary:
            SenderAddress.objects.filter(is_primary=True).update(is_primary=False)
        super().save_model(request, obj, form, change)


@admin.register(RecipientAddress)
class RecipientAddressAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_name', 'city', 'state', 'is_residential', 'is_verified', 'created_at')
    list_filter = ('is_residential', 'is_verified', 'state', 'country', 'created_at')
    search_fields = ('name', 'company_name', 'label_name', 'address1', 'city', 'email', 'phone', 'ifs_id')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_verified',)
    actions = ['verify_addresses', 'sync_from_ifs']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('ifs_id', 'name', 'company_name', 'label_name')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'zip_code', 'country')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email')
        }),
        ('Options', {
            'fields': ('is_residential', 'is_verified')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verify_addresses(self, request, queryset):
        """Verify selected addresses with IFS"""
        verified_count = 0
        failed_count = 0
        
        for recipient in queryset:
            try:
                ifs_service = IFSAPIService()
                result = ifs_service.verify_recipient_address({
                    'recipient_id': recipient.ifs_id,
                    'client_company_name': recipient.company_name or '',
                    'client_address1': recipient.address1,
                    'client_address2': recipient.address2 or '',
                    'client_city': recipient.city,
                    'client_state': recipient.state,
                    'client_country': recipient.country,
                    'client_zip': recipient.zip_code,
                })
                
                if result.get('status') == 1:
                    recipient.is_verified = True
                    recipient.save()
                    verified_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
        
        if verified_count > 0:
            self.message_user(request, f"Successfully verified {verified_count} addresses")
        if failed_count > 0:
            self.message_user(request, f"Failed to verify {failed_count} addresses", level=messages.WARNING)
    
    verify_addresses.short_description = "Verify selected addresses with IFS"
    
    def sync_from_ifs(self, request, queryset):
        """Sync recipient addresses from IFS"""
        try:
            ifs_service = IFSAPIService()
            result = ifs_service.get_recipient_list()
            
            synced_count = 0
            for recipient_data in result.get('recipient_list', []):
                # Get detailed recipient data
                detail_result = ifs_service.get_recipient_data(recipient_data['id'])
                recipient_detail = detail_result.get('recipient_data', {})
                
                # Update or create recipient address
                recipient, created = RecipientAddress.objects.update_or_create(
                    ifs_id=recipient_data['id'],
                    defaults={
                        'name': recipient_detail.get('client_name', ''),
                        'company_name': recipient_detail.get('client_company_name', ''),
                        'label_name': recipient_detail.get('client_label_name', ''),
                        'address1': recipient_detail.get('client_address1', ''),
                        'address2': recipient_detail.get('client_address2', ''),
                        'city': recipient_detail.get('client_city', ''),
                        'state': recipient_detail.get('client_state', ''),
                        'zip_code': recipient_detail.get('client_zip', ''),
                        'country': recipient_detail.get('client_country', 'United States'),
                        'phone': recipient_detail.get('client_phone', ''),
                        'email': recipient_detail.get('client_email', ''),
                        'is_residential': recipient_detail.get('is_residential') == 1,
                        'is_verified': recipient_detail.get('client_is_address_verify') == 0,  # 0 means verified in IFS
                    }
                )
                synced_count += 1
            
            self.message_user(request, f"Successfully synced {synced_count} recipient addresses from IFS")
            
        except Exception as e:
            self.message_user(request, f"Error syncing from IFS: {str(e)}", level=messages.ERROR)
    
    sync_from_ifs.short_description = "Sync recipient addresses from IFS"


class NotificationEmailInline(admin.TabularInline):
    model = NotificationEmail
    extra = 1
    fields = ('name', 'email', 'message')


class ShipmentProductInline(admin.TabularInline):
    model = ShipmentProduct
    extra = 1
    fields = ('name', 'description', 'quantity', 'gross_weight', 'weight_unit', 'value', 'origin_country')


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        'get_transaction_info', 'tracking_number', 'sender', 'recipient', 
        'status', 'service_type', 'shipping_cost', 'created_at'
    )
    list_filter = (
        'status', 'service_type', 'package_type', 'payment_type', 
        'is_international', 'saturday_delivery', 'created_at'
    )
    search_fields = (
        'tracking_number', 'ifs_shipment_id', 'reference',
        'sender__name', 'recipient__name', 'transaction_history__product'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'get_transaction_link', 'get_label_links',
        'ifs_shipment_id', 'tracking_number', 'zone_id'
    )
    inlines = [NotificationEmailInline, ShipmentProductInline]
    actions = ['void_shipments', 'refresh_tracking']
    raw_id_fields = ('transaction_history', 'sender', 'recipient')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('get_transaction_link', 'sender', 'recipient', 'status')
        }),
        ('IFS Information', {
            'fields': ('ifs_shipment_id', 'tracking_number', 'zone_id'),
            'classes': ('collapse',)
        }),
        ('Package Details', {
            'fields': (
                'package_type', 'service_type', 'package_weight',
                ('package_length', 'package_width', 'package_height'),
                'declared_value'
            )
        }),
        ('Shipment Options', {
            'fields': (
                'payment_type', 'account_number', 'signature_type',
                'saturday_delivery', 'hold_at_location'
            )
        }),
        ('Hold at Location', {
            'fields': (
                'hal_contact_person', 'hal_company_name', 'hal_address',
                'hal_city', 'hal_state', 'hal_zip_code', 'hal_phone',
                'hal_location_property'
            ),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': (
                'pickup_date', 'estimated_delivery', 'shipped_date', 'delivered_date'
            )
        }),
        ('Labels & Documents', {
            'fields': ('label_format', 'get_label_links')
        }),
        ('Cost & Reference', {
            'fields': ('shipping_cost', 'reference', 'reference_on_label')
        }),
        ('International Shipping', {
            'fields': ('is_international', 'duties_taxes_paid_by', 'customs_value'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def void_shipments(self, request, queryset):
        """Void selected shipments"""
        voided_count = 0
        failed_count = 0
        
        for shipment in queryset:
            if shipment.status in ['pending', 'label_created']:
                try:
                    ifs_service = IFSAPIService()
                    result = ifs_service.void_shipment(shipment.ifs_shipment_id)
                    
                    if result.get('status') == 1:
                        shipment.status = 'voided'
                        shipment.save()
                        voided_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    failed_count += 1
            else:
                failed_count += 1
        
        if voided_count > 0:
            self.message_user(request, f"Successfully voided {voided_count} shipments")
        if failed_count > 0:
            self.message_user(request, f"Failed to void {failed_count} shipments", level=messages.WARNING)
    
    void_shipments.short_description = "Void selected shipments"
    
    def refresh_tracking(self, request, queryset):
        """Refresh tracking information for selected shipments"""
        updated_count = 0
        
        for shipment in queryset:
            if shipment.ifs_shipment_id:
                try:
                    ifs_service = IFSAPIService()
                    result = ifs_service.get_shipment_details(shipment_id=shipment.ifs_shipment_id)
                    
                    if result.get('status') == 1:
                        shipment_info = result.get('package_shipment_info', {})
                        delivery_info = result.get('delivery_information', {})
                        
                        # Update status based on IFS data
                        fedex_status = shipment_info.get('fedex_status', '').lower()
                        if 'delivered' in fedex_status:
                            shipment.status = 'delivered'
                            if delivery_info.get('delivered_date'):
                                shipment.delivered_date = delivery_info['delivered_date']
                        elif 'transit' in fedex_status:
                            shipment.status = 'in_transit'
                        
                        shipment.save()
                        updated_count += 1
                        
                except Exception as e:
                    continue
        
        self.message_user(request, f"Successfully updated {updated_count} shipments")
    
    refresh_tracking.short_description = "Refresh tracking information"
    
    def get_transaction_info(self, obj):
        return f"{obj.transaction_history.product} (ID: {obj.transaction_history.id})"
    get_transaction_info.short_description = 'Transaction'
    get_transaction_info.admin_order_field = 'transaction_history__product'
    
    def get_transaction_link(self, obj):
        if obj.transaction_history:
            url = reverse('admin:transactions_transactionhistory_change', 
                         args=[obj.transaction_history.id])
            return format_html('<a href="{}">{} (ID: {})</a>', 
                             url, obj.transaction_history.product, obj.transaction_history.id)
        return "No transaction linked"
    get_transaction_link.short_description = 'Transaction'
    
    def get_label_links(self, obj):
        links = []
        if obj.label_url:
            links.append(f'<a href="{obj.label_url}" target="_blank">Label</a>')
        if obj.commercial_invoice_url:
            links.append(f'<a href="{obj.commercial_invoice_url}" target="_blank">Commercial Invoice</a>')
        if obj.return_label_url:
            links.append(f'<a href="{obj.return_label_url}" target="_blank">Return Label</a>')
        if obj.receipt_url:
            links.append(f'<a href="{obj.receipt_url}" target="_blank">Receipt</a>')
        
        if links:
            return mark_safe(' | '.join(links))
        return "No documents available"
    get_label_links.short_description = 'Documents'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'transaction_history', 'sender', 'recipient'
        )


@admin.register(NotificationEmail)
class NotificationEmailAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'get_shipment_info', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('email', 'name', 'shipment__tracking_number')
    readonly_fields = ('created_at',)
    raw_id_fields = ('shipment',)
    
    def get_shipment_info(self, obj):
        return f"Tracking: {obj.shipment.tracking_number or 'N/A'}"
    get_shipment_info.short_description = 'Shipment'
    get_shipment_info.admin_order_field = 'shipment__tracking_number'


@admin.register(ShipmentProduct)
class ShipmentProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'get_shipment_info', 'quantity', 'gross_weight', 
        'weight_unit', 'value', 'origin_country', 'created_at'
    )
    list_filter = ('weight_unit', 'origin_country', 'created_at')
    search_fields = (
        'name', 'description', 'hts_number', 
        'shipment__tracking_number', 'shipment__recipient__name'
    )
    readonly_fields = ('created_at',)
    raw_id_fields = ('shipment',)
    
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
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_shipment_info(self, obj):
        return f"Tracking: {obj.shipment.tracking_number or 'N/A'}"
    get_shipment_info.short_description = 'Shipment'
    get_shipment_info.admin_order_field = 'shipment__tracking_number'


# Custom admin site configuration
admin.site.site_header = "Shipping Management Admin"
admin.site.site_title = "Shipping Admin"
admin.site.index_title = "Welcome to Shipping Management"