from django.db import models
from django.utils import timezone
from auth_.models import User

class Brand(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class WatchModel(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='models')
    name = models.CharField(max_length=100)
    reference_number = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.brand.name} {self.name}"

class Watch(models.Model):
    CONDITION_CHOICES = (
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
    )
    
    STATUS_CHOICES = (
        ('in_stock', 'In Stock'),
        ('sold', 'Sold'),
        ('reserved', 'Reserved'),
        ('consignment', 'Consignment'),
    )
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watches')
    watch_model = models.ForeignKey(WatchModel, on_delete=models.CASCADE, related_name='watches')
    serial_number = models.CharField(max_length=50, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField()
    purchase_notes = models.TextField(blank=True, null=True)
    asking_price = models.DecimalField(max_digits=10, decimal_places=2)
    box = models.BooleanField(default=False)
    papers = models.BooleanField(default=False)
    certificate = models.BooleanField(default=False)
    images = models.JSONField(default=list)  # Store image URLs
    description = models.TextField(blank=True, null=True)
    additional_info = models.JSONField(default=dict)  # For flexible additional data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.watch_model} - {self.serial_number}"
    
    @property
    def days_in_inventory(self):
        if self.status == 'in_stock':
            return (timezone.now().date() - self.purchase_date).days
        return None
    
    @property
    def stock_age_category(self):
        days = self.days_in_inventory
        if days is None:
            return None
        if days < 30:
            return 'less_than_30'
        elif days < 60:
            return '30_to_60'
        elif days < 90:
            return '60_to_90'
        else:
            return 'more_than_90'