from django.db import models
from transactions.models import TransactionHistory

class Shipment(models.Model):
    """Shipping information for transactions"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('label_created', 'Label Created'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
    )
    
    transaction_history = models.OneToOneField(TransactionHistory, on_delete=models.CASCADE, related_name='shipment')
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    carrier = models.CharField(max_length=100)
    shipping_method = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    estimated_delivery = models.DateField(blank=True, null=True)
    shipped_date = models.DateField(blank=True, null=True)
    delivered_date = models.DateField(blank=True, null=True)
    shipping_address = models.JSONField(default=dict)
    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2)
    label_url = models.URLField(blank=True, null=True)
    tracking_history = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Shipment for {self.transaction_history.product} - {self.tracking_number}"
