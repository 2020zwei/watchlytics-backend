from django.contrib import admin
from .models import TransactionHistory

@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_type', 'product', 'amount', 'date', 'sale_category', 'customer')
    list_filter = ('transaction_type', 'sale_category', 'date')
    search_fields = ('product__name', 'notes', 'customer__name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')