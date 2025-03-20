from django.contrib import admin
from .models import Customer, Interaction

class InteractionInline(admin.TabularInline):
    model = Interaction
    extra = 1

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'phone')
    inlines = [InteractionInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'email', 'phone')
        }),
        ('Additional Information', {
            'fields': ('address', 'notes'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'interaction_type', 'date', 'follow_up_date', 'follow_up_completed')
    list_filter = ('interaction_type', 'follow_up_completed', 'date')
    search_fields = ('customer__name', 'notes')
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'customer', 'interaction_type', 'date')
        }),
        ('Interaction Details', {
            'fields': ('notes',)
        }),
        ('Follow Up', {
            'fields': ('follow_up_date', 'follow_up_completed'),
            'classes': ('collapse',)
        }),
    )
