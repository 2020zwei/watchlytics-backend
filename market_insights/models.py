from django.db import models
from inventory.models import Product

class MarketData(models.Model):
    """Market data scraped from various sources"""
    SOURCE_CHOICES = (
        ('ebay', 'eBay'),
        ('chrono24', 'Chrono24'),
        ('bezel', 'Bezel'),
        ('grailzee', 'Grailzee'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='market_data', null=True, blank=True)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    item_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    product_url = models.URLField(blank=True, null=True)
    listing_url = models.URLField(blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    scraped_at = models.DateTimeField(auto_now_add=True)
    listing_date = models.DateField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True)
    condition = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.product} - {self.source} - {self.price}"