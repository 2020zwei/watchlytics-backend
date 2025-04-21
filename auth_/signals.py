import stripe
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from auth_.models import User
import os

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

@receiver(post_save, sender=User)
def create_stripe_customer(sender, instance, created, **kwargs):
    if created:
        customer = stripe.Customer.create(
            email=instance.email,
            name=instance.get_full_name() or instance.email,
        )

        instance.stripe_customer_id = customer.id
        instance.save(update_fields=['stripe_customer_id'])
