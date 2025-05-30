from django.db import models
from auth_.models import User
from inventory.models import Product
from customers.models import Customer
from decimal import Decimal

class TransactionHistory(models.Model):
    """Base transaction model"""
    TRANSACTION_TYPE_CHOICES = (
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
    )
    
    SALE_CATEGORY_CHOICES = (
        ('personal', 'Personal Sale'),
        ('dealer', 'Dealer Sale'),
        ('marketplace', 'Marketplace Listing'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions_user')
    name_of_trade = models.CharField(max_length=255, blank=True, null=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    date = models.DateField()
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    sale_category = models.CharField(max_length=20, choices=SALE_CATEGORY_CHOICES, blank=True, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, related_name='transactions_customer', null=True, blank=True)
    
    expenses = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name_of_trade or self.transaction_type} - {self.date}"
    
    @property
    def total_purchase_price(self):
        return sum((item.total_purchase_price or Decimal('0')) for item in self.transaction_items.all())
    
    @property
    def total_sale_price(self):
        return sum((item.total_sale_price or Decimal('0')) for item in self.transaction_items.all())
    
    @property
    def profit(self):
        if self.transaction_type != 'sale':
            return Decimal('0')
        
        return self.total_sale_price - self.total_purchase_price


class TransactionItem(models.Model):
    transaction = models.ForeignKey(TransactionHistory, on_delete=models.CASCADE, related_name='transaction_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transaction_items')
    quantity = models.IntegerField(default=1)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    def __str__(self):
        return f"{self.product.model_name} - {self.quantity}"
    
    @property
    def total_purchase_price(self):
        if self.quantity is None or self.purchase_price is None:
            return Decimal('0')
        return Decimal(self.quantity) * Decimal(self.purchase_price)
    
    @property
    def total_sale_price(self):
        if self.quantity is None or self.sale_price is None:
            return Decimal('0')
        return Decimal(self.quantity) * Decimal(self.sale_price)