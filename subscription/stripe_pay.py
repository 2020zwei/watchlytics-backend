import re

import stripe
from django.contrib.auth import get_user_model
import os

from subscription.models import Subscription
# Configure stripe API key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')


User = get_user_model()

def get_user_subscriptions_by_status(user, status):
    """
    Helper function to get subscriptions by their status.
    """
    stripe_customer_id = user.stripe_customer_id  # Using your user model's field
    subscriptions = stripe.Subscription.list(customer=stripe_customer_id, status=status)
    return subscriptions


def create_customer(email):
    try:
        customer = stripe.Customer.create(
            email=email,
        )
        return {'status': True, 'result': customer.id}
    except stripe.error.StripeError as e:
        return {'status': False, 'result': e}


def get_payment_method_id(payment_method):
    try:
        # Retrieve payment method details by ID
        payment_method_details = stripe.PaymentMethod.retrieve(payment_method)

        # Extract the PaymentMethod ID
        payment_method_id = payment_method_details.id

        return {'status': True, 'result': payment_method_id}
    except stripe.error.StripeError as e:
        return {'status': False, 'result': e}


def attach_payment_method(customer_id, payment_method_id):
    try:
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
        )

        stripe.Customer.modify(
            customer_id,
            invoice_settings={
                'default_payment_method': payment_method_id
            }
        )
        return {'status': True, 'result': True}
    except stripe.error.StripeError as e:
        return {'status': False, 'result': e}


def create_subscription(customer_id, price_id):
    try:
        # Check if a free subscription already exists
        user = User.objects.filter(stripe_customer_id=customer_id).first()
        
        # Check if an active subscription exists already
        existing_free_sub = Subscription.objects.filter(
            user=user, 
            plan__name='FREE', 
            is_active=True
        ).first()

        # If no free subscription exists, apply a trial period
        trial_period = None if existing_free_sub else 7

        subscription_params = {
            'customer': customer_id,
            'items': [{"price": price_id}],
            'cancel_at_period_end': False,
        }
        
        # Only add trial period if it's not None
        if trial_period:
            subscription_params['trial_period_days'] = trial_period
            
        subscription_intent = stripe.Subscription.create(**subscription_params)
        
        return {'status': True, 'result': subscription_intent}
    except stripe.error.StripeError as e:
        return {'status': False, 'result': e}


def make_stripe_order_payment(data):
    payment_method_str = data['payment_method_token']

    get_payment_method = get_payment_method_id(payment_method_str)

    if get_payment_method.get('status') is False:
        message = get_payment_method.get('result').user_message
        return {'success': False, 'message': f'{message}'}
    else:
        payment_method_id = get_payment_method.get('result')
        user = User.objects.filter(id=data['user_id']).first()
        
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer = create_customer(user.email)

            if customer.get('status') is False:
                message = customer.get('result').user_message
                cleaned_error_message = re.sub(r'\bcus_\w+', '', message)
                return {'success': False, 'message': f'{cleaned_error_message}'}
            else:
                customer_id = customer.get('result')
                user.stripe_customer_id = customer_id
                user.save()

        payment_method_modify = attach_payment_method(customer_id, payment_method_id)

        if payment_method_modify.get('status') is False:
            message = payment_method_modify.get('result').user_message
            cleaned_error_message = re.sub(r'\bpm_\w+', '', message)
            return {'success': False, 'message': f'{cleaned_error_message}'}
        else:
            intent = create_subscription(customer_id, data['price_id'])
            if intent.get('status') is False:
                message = intent.get('result').user_message
                cleaned_error_message = re.sub(r'\bsub_\w+', '', message)
                return {'success': False, 'message': f'{cleaned_error_message}'}
            else:
                status = intent.get('result').status
                if status == 'active' or status == 'trialing':
                    return {
                        'success': True, 
                        'message': 'Subscription successfully completed.',
                        'intent_id': intent.get('result').id,
                        'stripe_subscription_id': intent.get('result').id,
                        'price': int(intent['result']['plan']['amount'] / 100)
                    }
                else:
                    return {'success': False, 'message': f'Failed to activate subscription. Status: {status}'}


def validate_stripe_fields(data):
    return all([
        data.get('price_id'),
        data.get('plan_name'),
    ])

