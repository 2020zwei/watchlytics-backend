from django.db import models
from django.utils import timezone
from auth_.models import User
from datetime import datetime
from django.core.validators import MinValueValidator

def product_image_path(instance, filename):
    return f'products/{instance.id}/{filename}'

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    AVAILABILTY_CHOICES = (
        ('in_stock', 'In Stock'),
        ('sold', 'Sold'),
        ('reserved', 'Reserved'),
        ('in_repair', 'In Repair'), 
    )

    CONDITION_CHOICES = (
        ('new', 'New'),
        ('used', 'Used'),
    )
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    model_name = models.CharField(max_length=200, blank=True, null=True)
    product_id = models.CharField(max_length=50)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    availability = models.CharField(max_length=20, choices=AVAILABILTY_CHOICES, default='in_stock')
    
    # Price information
    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    repair_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    msrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    sold_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    website_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    profit_margin = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    profit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Quantity and unit
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    unit = models.CharField(max_length=50, blank=True, null=True)
    
    # Dates
    date_purchased = models.DateTimeField()
    date_sold = models.DateTimeField(blank=True, null=True)
    hold_time = models.IntegerField(blank=True, null=True)
    
    # Source information
    source_of_sale = models.CharField(max_length=100, blank=True, null=True)
    delivery_content = models.CharField(max_length=100, blank=True, null=True)
    condition = models.CharField(max_length=50, blank=True, null=True, choices=CONDITION_CHOICES, default='new')
    purchased_from = models.CharField(max_length=100, blank=True, null=True)
    sold_source = models.CharField(max_length=100, blank=True, null=True)
    is_sold = models.BooleanField(default=False)
    # Listing information
    listed_on = models.CharField(max_length=200, blank=True, null=True)
    
    # Media
    image = models.ImageField(upload_to='images/', blank=True, null=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    serial_number = models.CharField(max_length=50, blank=True, null=True)

    year = models.PositiveIntegerField(
        choices=[(r, r) for r in range(1900, datetime.now().year + 1)],
        verbose_name="Year",
        default=datetime.now().year,
        blank=False,
        null=False
    )
    class Meta:
        unique_together = (('owner', 'product_id'))
    
    def __str__(self):
        return f"{self.model_name} ({self.product_id})"
    
    def get_image_url(self):
        if self.image:
            return self.image.url
        return None 
    @property
    def days_in_inventory(self):
        if self.availability == 'in_stock':
            return (timezone.now().date() - self.date_purchased.date()).days
        elif not self.date_sold:
            return (timezone.now().date() - self.date_purchased.date()).days
        return (self.date_sold - self.date_purchased).days
    
    # @property
    # def is_sold(self):
    #     return self.date_sold is not None
    
    @property
    def calculated_profit(self):
        if not self.sold_price:
            return None
        
        total_cost = self.buying_price
        if self.shipping_price:
            total_cost += self.shipping_price
        if self.repair_cost:
            total_cost += self.repair_cost
        if self.fees:
            total_cost += self.fees
        if self.commission:
            total_cost += self.commission
            
        return self.sold_price - total_cost
    
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