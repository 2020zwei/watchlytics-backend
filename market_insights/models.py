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
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='market_data')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    listing_url = models.URLField(blank=True, null=True)
    condition = models.CharField(max_length=50, blank=True, null=True)
    listing_date = models.DateField()
    additional_info = models.JSONField(default=dict)
    scraped_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.product} - {self.source} - {self.price}"