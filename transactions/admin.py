from django.contrib import admin
from .models import TransactionHistory, TransactionItem


class TransactionItemInline(admin.TabularInline):
    model = TransactionItem
    extra = 1
    fields = ('product', 'quantity', 'purchase_price', 'sale_price', 'total_purchase_price', 'total_sale_price')
    readonly_fields = ('total_purchase_price', 'total_sale_price')


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_of_trade', 'transaction_type', 'formatted_items', 'purchase_price', 'sale_price', 'date', 'sale_category', 'customer')
    list_filter = ('transaction_type', 'sale_category', 'date')
    search_fields = ('name_of_trade', 'transaction_items__product__name', 'notes', 'customer__name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at', 'total_purchase_price', 'total_sale_price', 'profit')
    inlines = [TransactionItemInline]
    fieldsets = (
        (None, {
            'fields': ('user', 'name_of_trade', 'transaction_type', 'date', 'purchase_price', 'sale_price', 'total_purchase_price', 'total_sale_price')
        }),
        ('Sale Information', {
            'fields': ('sale_category', 'customer', 'profit'),
            'classes': ('collapse',),
        }),
        ('Additional Information', {
            'fields': ('notes', 'expenses', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def formatted_items(self, obj):
        """Return a comma-separated list of product names in the transaction"""
        items = obj.transaction_items.all()
        if not items:
            return "-"
        items_list = [f"{item.product.product_name} (x{item.quantity})" for item in items[:3]]
        if len(items) > 3:
            items_list.append(f"and {len(items) - 3} more")
        return ", ".join(items_list)
    formatted_items.short_description = "Products"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('transaction_items', 'transaction_items__product')


@admin.register(TransactionItem)
class TransactionItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_link', 'product', 'quantity', 'purchase_price', 'sale_price', 'total_purchase_price', 'total_sale_price')
    list_filter = ('transaction__transaction_type', 'product')
    search_fields = ('product__name', 'transaction__name_of_trade', 'transaction__notes')
    readonly_fields = ('total_purchase_price', 'total_sale_price')

    def transaction_link(self, obj):
        """Return a link to the transaction"""
        url = f"/admin/yourapp/transactionhistory/{obj.transaction.id}/change/"
        return f'<a href="{url}">{obj.transaction}</a>'
    transaction_link.short_description = "Transaction"
    transaction_link.allow_tags = True