from django.contrib import admin
# from .models import TransactionHistory

# @admin.register(TransactionHistory)
# class TransactionAdmin(admin.ModelAdmin):
#     # list_display = ('transaction_type', 'product', 'amount', 'date', 'sale_category', 'profit')
#     list_filter = ('transaction_type', 'sale_category', 'date')
#     # search_fields = ('product_product_id', 'product_name', 'customer__name')
#     readonly_fields = ('profit',)
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('user', 'product', 'transaction_type', 'amount', 'date')
#         }),
#         ('Sale Information', {
#             'fields': ('sale_category', 'customer'),
#             'classes': ('collapse',)
#         }),
#         ('Expenses', {
#             'fields': ('expenses',),
#             'classes': ('collapse',)
#         }),
#         ('Notes', {
#             'fields': ('notes',),
#             'classes': ('collapse',)
#         }),
#         ('Financial', {
#             'fields': ('profit',),
#             'classes': ('collapse',)
#         }),
#     )