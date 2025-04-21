from django.db import models
from auth_.models import User

class Plan(models.Model):
    """Subscription plan details"""
    PLAN_TYPES = (
        ('FREE', 'Free'),
        ('BASIC', 'Basic'),
        ('ADVANCED', 'Advanced'),
        ('PRO', 'Pro'),
    )
    
    name = models.CharField(max_length=50, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField()
    features = models.JSONField(default=list, blank=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    is_popular = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} - ${self.price}"

class Subscription(models.Model):
    """User subscription information"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
        ('unpaid', 'Unpaid'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_trial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.user.first_name} - {self.plan.name}"
