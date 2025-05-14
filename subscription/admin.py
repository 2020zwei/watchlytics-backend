from django.contrib import admin
from .models import Plan, Subscription, UserCard

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'stripe_price_id')
    search_fields = ('name', 'stripe_price_id')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'end_date', 'is_trial')
    list_filter = ('status', 'plan', 'is_trial')
    search_fields = ('user__username', 'user__email', 'stripe_subscription_id')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'plan')
        }),
        ('Subscription Details', {
            'fields': ('status', 'start_date', 'end_date', 'is_trial')
        }),
        ('Stripe Information', {
            'fields': ('stripe_subscription_id',),
            'classes': ('collapse',)
        }),
    )

@admin.register(UserCard)
class UserCardAdmin(admin.ModelAdmin):
    list_display = ('user', 'card_brand', 'last_four', 'is_default', 'created_at')
    list_filter = ('card_brand', 'is_default')
    search_fields = ('user__username', 'user__email', 'card_holder_name', 'stripe_payment_method_id')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'card_holder_name')
        }),
        ('Card Details', {
            'fields': ('card_brand', 'last_four', 'exp_month', 'exp_year', 'is_default')
        }),
        ('Stripe Information', {
            'fields': ('stripe_payment_method_id',),
            'classes': ('collapse',)
        }),
    )