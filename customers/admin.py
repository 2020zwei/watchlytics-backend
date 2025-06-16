from django.contrib import admin
from django.utils.html import format_html
from .models import Customer, CustomerTag, FollowUp, Interaction
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.safestring import mark_safe

class InteractionInline(admin.TabularInline):
    model = Interaction
    extra = 1
    fields = ('interaction_type', 'date', 'notes', 'follow_up_date', 'follow_up_completed')
    readonly_fields = ('created_at', 'updated_at')

class FollowUpInline(admin.TabularInline):
    model = FollowUp
    extra = 1
    fields = ('due_date', 'notes', 'status')
    readonly_fields = ('completed_at', 'created_at', 'updated_at')

class CustomerTagInline(admin.TabularInline):
    model = CustomerTag.customers.through
    extra = 1
    verbose_name = "Tag"
    verbose_name_plural = "Tags"

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'profile_picture_thumbnail',
        'name', 
        'email', 
        'phone', 
        'status_badge',
        'total_orders_display',
        'total_spent_display',
        'last_purchase_display',
        'created_at'
    )
    list_display_links = ('profile_picture_thumbnail', 'name')
    search_fields = ('name', 'email', 'phone', 'address', 'notes')
    list_filter = (
        'status',
        'created_at',
        'tags',
        ('user', admin.RelatedOnlyFieldListFilter),
    )
    inlines = [CustomerTagInline, InteractionInline, FollowUpInline]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user', 
                'profile_picture_display',
                'name', 
                'email', 
                'phone',
                'status'
            )
        }),
        ('Additional Information', {
            'fields': ('address', 'notes', 'profile_picture'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('profile_picture_display',)
    actions = ['mark_active', 'mark_inactive', 'export_customer_data']
    filter_horizontal = ['tags']
    date_hierarchy = 'created_at'
    save_on_top = True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            _total_orders=Count('transactions_customer', distinct=True),
            _total_spent=Sum('transactions_customer__sale_price')
        )
        return qs
    
    def profile_picture_thumbnail(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover;" />',
                obj.profile_picture.url
            )
        return format_html(
            '<div style="width:50px; height:50px; border-radius:50%; background:#eee; display:flex; align-items:center; justify-content:center;">{}</div>',
            obj.name[0].upper() if obj.name else '?'
        )
    profile_picture_thumbnail.short_description = ''
    profile_picture_thumbnail.admin_order_field = 'name'
    
    def profile_picture_display(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="100" height="100" style="border-radius: 50%; object-fit: cover;" />',
                obj.profile_picture.url
            )
        return "No image"
    profile_picture_display.short_description = 'Current Profile Picture'
    
    def status_badge(self, obj):
        color = 'green' if obj.status else 'red'
        text = 'Active' if obj.status else 'Inactive'
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:10px; font-size:12px;">{}</span>',
            color, text
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def total_orders_display(self, obj):
        if hasattr(obj, '_total_orders'):
            url = reverse('admin:sales_transaction_changelist') + f'?customer__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, obj._total_orders)
        return 0
    total_orders_display.short_description = 'Orders'
    total_orders_display.admin_order_field = '_total_orders'
    
    def total_spent_display(self, obj):
        total = getattr(obj, '_total_spent', 0) or 0
        return f"${total:,.2f}"
    total_spent_display.short_description = 'Total Spent'
    total_spent_display.admin_order_field = '_total_spent'
    
    def last_purchase_display(self, obj):
        if obj.last_purchase:
            return obj.last_purchase.date.strftime('%Y-%m-%d')
        return 'Never'
    last_purchase_display.short_description = 'Last Purchase'
    
    def mark_active(self, request, queryset):
        updated = queryset.update(status=True)
        self.message_user(request, f"{updated} customers marked as active.")
    mark_active.short_description = "Mark selected customers as active"
    
    def mark_inactive(self, request, queryset):
        updated = queryset.update(status=False)
        self.message_user(request, f"{updated} customers marked as inactive.")
    mark_inactive.short_description = "Mark selected customers as inactive"
    
    def export_customer_data(self, request, queryset):
        # This would be implemented with a proper export function
        self.message_user(request, f"Preparing export for {queryset.count()} customers.")
    export_customer_data.short_description = "Export selected customers"
    
    def get_list_filter(self, request):
        list_filter = super().get_list_filter()
        if not request.user.is_superuser:
            # Remove user filter for non-superusers
            list_filter = [f for f in list_filter if f != 'user']
        return list_filter
    
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            # Remove user field for non-superusers
            fieldsets = list(fieldsets)
            fieldsets[0][1]['fields'] = tuple(
                f for f in fieldsets[0][1]['fields'] if f != 'user'
            )
        return fieldsets

@admin.register(CustomerTag)
class CustomerTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_display', 'customer_count')
    search_fields = ('name',)
    list_filter = ('user',)
    filter_horizontal = ('customers',)
    
    def color_display(self, obj):
        return format_html(
            '<div style="width:20px; height:20px; background:{}; border:1px solid #ccc;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'
    
    def customer_count(self, obj):
        return obj.customers.count()
    customer_count.short_description = 'Customers'

@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ('customer_link', 'due_date', 'status', 'days_overdue')
    list_filter = ('status', 'due_date', 'user')
    search_fields = ('customer__name', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    date_hierarchy = 'due_date'
    
    def customer_link(self, obj):
        url = reverse('admin:customers_customer_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.name)
    customer_link.short_description = 'Customer'
    customer_link.admin_order_field = 'customer__name'
    
    def days_overdue(self, obj):
        if obj.status == 'pending' and obj.due_date:
            from django.utils import timezone
            delta = timezone.now().date() - obj.due_date
            if delta.days > 0:
                return format_html(
                    '<span style="color:red;">{} days</span>',
                    delta.days
                )
        return ''
    days_overdue.short_description = 'Overdue'

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = (
        'customer_link',
        'interaction_type',
        'date',
        'user_link',
        'follow_up_status'
    )
    list_filter = (
        'interaction_type',
        'follow_up_completed',
        ('date', admin.DateFieldListFilter),
        'user'
    )
    search_fields = ('customer__name', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    
    def customer_link(self, obj):
        url = reverse('admin:customers_customer_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.name)
    customer_link.short_description = 'Customer'
    customer_link.admin_order_field = 'customer__name'
    
    def user_link(self, obj):
        url = reverse('admin:auth__user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def follow_up_status(self, obj):
        if obj.follow_up_date:
            color = 'green' if obj.follow_up_completed else 'orange'
            text = 'Completed' if obj.follow_up_completed else f'Due {obj.follow_up_date}'
            return format_html(
                '<span style="background:{}; color:white; padding:2px 6px; border-radius:10px; font-size:12px;">{}</span>',
                color, text
            )
        return ''
    follow_up_status.short_description = 'Follow Up'