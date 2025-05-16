from django.db import models
from auth_.models import User


class CustomerManager(models.Manager):
    def active(self):
        return self.filter(status=True)

    def inactive(self):
        return self.filter(status=False)
    
class Customer(models.Model):
    """Customer information for CRM"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.BooleanField(default=True)
    def __str__(self):
        return self.name
class Interaction(models.Model):
    """Customer interaction logging"""
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