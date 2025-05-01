from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TransactionHistory
from inventory.models import ProductInventory

@receiver(post_save, sender=TransactionHistory)
def update_inventory_on_transaction(sender, instance, created, **kwargs):
    if created:
        inventory, _ = ProductInventory.objects.get_or_create(
            product=instance.product, 
            defaults={'quantity': 0}
        )
        
        if instance.transaction_type == 'purchase':
            inventory.quantity += 1
        elif instance.transaction_type == 'sale':
            inventory.quantity -= 1
        
        inventory.save()

@receiver(post_delete, sender=TransactionHistory)
def revert_inventory_on_delete(sender, instance, **kwargs):
    try:
        inventory = ProductInventory.objects.get(product=instance.product)
        
        if instance.transaction_type == 'purchase':
            inventory.quantity -= 1
        elif instance.transaction_type == 'sale':
            inventory.quantity += 1
            
        inventory.save()
    except ProductInventory.DoesNotExist:
        pass