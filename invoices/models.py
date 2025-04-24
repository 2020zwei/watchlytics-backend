from django.db import models
from auth_.models import User
from transactions.models import TransactionHistory

class Invoice(models.Model):
    """Invoice generation and management"""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('canceled', 'Canceled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    transaction_history = models.OneToOneField(TransactionHistory, on_delete=models.CASCADE, related_name='invoice')
    invoice_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(blank=True, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    company_info = models.JSONField(default=dict)
    customer_info = models.JSONField(default=dict)
    pdf_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.transaction_history.product}"