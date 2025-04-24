from django.db import models
from django.utils import timezone
from auth_.models import User


def product_image_path(instance, filename):
    return f'products/{instance.id}/{filename}'

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    STATUS_CHOICES = (
        ('in_stock', 'In Stock'),
        ('sold', 'Sold'),
        ('reserved', 'Reserved'),
    )
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    product_name = models.CharField(max_length=200)
    product_id = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    
    # Price information
    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    repair_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    msrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    sold_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    whole_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    website_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    profit_margin = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Quantity and unit
    quantity = models.IntegerField(default=1)
    unit = models.CharField(max_length=50, blank=True, null=True)
    
    # Dates
    date_purchased = models.DateField()
    purchase_date = models.DateField(default=timezone.now)
    date_sold = models.DateField(blank=True, null=True)
    hold_time = models.IntegerField(blank=True, null=True)
    
    # Source information
    source_of_sale = models.CharField(max_length=100, blank=True, null=True)
    purchased_from = models.CharField(max_length=100, blank=True, null=True)
    sold_source = models.CharField(max_length=100, blank=True, null=True)
    
    # Listing information
    listed_on = models.CharField(max_length=200, blank=True, null=True)
    
    # Media
    image = models.ImageField(upload_to='images/', blank=False, null=False)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('owner', 'product_id')
    
    def __str__(self):
        return f"{self.product_name} ({self.product_id})"
    
    def get_image_url(self):
        if self.image:
            return self.image.url
        return None 
    @property
    def days_in_inventory(self):
        if self.status == 'in_stock':
            return (timezone.now().date() - self.purchase_date).days
        elif not self.date_sold:
            return (timezone.now().date() - self.date_purchased).days
        return (self.date_sold - self.date_purchased).days
    
    @property
    def is_sold(self):
        return self.date_sold is not None
    
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