from django.db import models
from auth_.models import User

class Plan(models.Model):
    """Subscription plan details"""
    PLAN_TYPE_CHOICES = (
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('basic_plus', 'Basic+'),
        ('pro', 'Pro'),
        ('business', 'Business'),
    )
    
    name = models.CharField(max_length=50, choices=PLAN_TYPE_CHOICES)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField()
    features = models.JSONField(default=list)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    
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
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
