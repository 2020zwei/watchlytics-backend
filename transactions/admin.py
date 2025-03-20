from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'watch', 'amount', 'date', 'sale_category', 'profit')
    list_filter = ('transaction_type', 'sale_category', 'date')
    search_fields = ('watch__serial_number', 'watch__watch_model__name', 'customer__name')
    readonly_fields = ('profit',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'watch', 'transaction_type', 'amount', 'date')
        }),
        ('Sale Information', {
            'fields': ('sale_category', 'customer'),
            'classes': ('collapse',)
        }),
        ('Expenses', {
            'fields': ('expenses',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Financial', {
            'fields': ('profit',),
            'classes': ('collapse',)
        }),
    )