from django.db import models
from auth_.models import User


class CustomerManager(models.Manager):
    def active(self):
        return self.filter(status=True)

    def inactive(self):
        return self.filter(status=False)
    
    def with_transaction_data(self):
        from django.db.models import Count, Sum, Max, Q
        from django.db.models.functions import Coalesce
        
        return self.annotate(
            orders_count=Count('transactions_customer', distinct=True),
            last_purchase_date=Max('transactions_customer__date'),
            total_spending=Coalesce(
                Sum('transactions_customer__sale_price', 
                    filter=Q(transactions_customer__transaction_type='sale')), 
                models.Value(0)
            )
        )
    
    def top_spenders(self, limit=10):
        return self.with_transaction_data().order_by('-total_spending')[:limit]
    
    def needs_follow_up(self):
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now().date() - timedelta(days=90)
        
        return self.with_transaction_data().filter(
            models.Q(last_purchase_date__lt=cutoff_date) | 
            models.Q(last_purchase_date__isnull=True)
        )
class Customer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.BooleanField(default=True)
    
    objects = CustomerManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'email'],
                name='unique_user_customer_email',
                condition=models.Q(email__isnull=False)
            )
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def is_active(self):
        return self.status
    
    @property
    def has_transactions(self):
        return self.transactions_customer.exists()
    
    @property
    def total_orders(self):
        return self.transactions_customer.count()
    
    @property
    def total_spent(self):
        from django.db.models import Sum, Q
        return self.transactions_customer.filter(
            Q(transaction_type='sale')
        ).aggregate(total=Sum('sale_price'))['total'] or 0
    
    @property
    def last_purchase(self):
        return self.transactions_customer.order_by('-date').first()
    
    def mark_inactive(self):
        self.status = False
        self.save(update_fields=['status'])
        return self
    
    def mark_active(self):
        self.status = True
        self.save(update_fields=['status'])
        return self
    
    def toggle_status(self):
        self.status = not self.status
        self.save(update_fields=['status'])
        return self

class CustomerTag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_tags')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default='#3498db')  # Default blue color
    customers = models.ManyToManyField(Customer, related_name='tags')
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = ('user', 'name')


class FollowUp(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follow_ups')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='follow_ups')
    due_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Follow up with {self.customer.name} on {self.due_date}"
    
    def mark_completed(self):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
        return self
class Interaction(models.Model):
    INTERACTION_TYPE_CHOICES = (
        ('email', 'Email'),
        ('call', 'Phone Call'),
        ('meeting', 'Meeting'),
        ('message', 'Message'),
        ('other', 'Other'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='interactions')
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES)
    date = models.DateTimeField()
    notes = models.TextField()
    follow_up_date = models.DateField(blank=True, null=True)
    follow_up_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.interaction_type} with {self.customer.name} on {self.date}"