from django.db import models
from auth_.models import User
from inventory.models import Product
from customers.models import Customer

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
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions_product')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    
    sale_category = models.CharField(max_length=20, choices=SALE_CATEGORY_CHOICES, blank=True, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, related_name='transactions_customer', null=True, blank=True)
    
    expenses = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.transaction_type} - {self.product} - {self.amount}"
    
    @property
    def profit(self):
        """Calculate profit if it's a sale transaction"""
        if self.transaction_type == 'sale':
            purchase_price = self.product.buying_price
            
            total_expenses = sum(expense['amount'] for expense in self.expenses.values())
            
            return self.amount - purchase_price - total_expenses