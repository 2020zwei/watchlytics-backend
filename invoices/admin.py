from django.contrib import admin
from .models import Invoice

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'transaction', 'status', 'issue_date', 'due_date', 'total')
    list_filter = ('status', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'transaction__watch__serial_number')
    readonly_fields = ('total',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'transaction', 'invoice_number', 'status')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'paid_date')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'tax_rate', 'tax_amount', 'total')
        }),
        ('Additional Information', {
            'fields': ('notes', 'terms', 'company_info', 'customer_info'),
            'classes': ('collapse',)
        }),
        ('Document', {
            'fields': ('pdf_url',),
            'classes': ('collapse',)
        }),
    )
