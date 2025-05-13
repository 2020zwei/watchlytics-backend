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
    except stripe.error.CardError as e:
        err = e.json_body.get('error', {})
        return {
            'status': False, 
            'result': e,
            'card_declined': True,
            'decline_code': err.get('decline_code'),
            'message': err.get('message', 'Your card was declined.')
        }
    except stripe.error.StripeError as e:
        return {'status': False, 'result': e}


def modify_subscription(stripe_subscription_id, new_price_id, payment_method_id=None):
    try:
        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        subscription_item_id = stripe_subscription['items']['data'][0]['id']
        
        modify_params = {
            'cancel_at_period_end': False,
            'proration_behavior': "always_invoice",
            'items': [{
                'id': subscription_item_id,
                'price': new_price_id
            }],
            'metadata': {"price_id": new_price_id, "is_upgrade": True}
        }
        
        if payment_method_id:
            modify_params['default_payment_method'] = payment_method_id
        
        response = stripe.Subscription.modify(
            stripe_subscription_id,
            **modify_params
        )
        
        return {'status': True, 'result': response}
    except stripe.error.CardError as e:
        err = e.json_body.get('error', {})
        return {
            'status': False, 
            'result': e,
            'card_declined': True,
            'decline_code': err.get('decline_code'),
            'message': err.get('message', 'Your card was declined.')
        }
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
                if intent.get('card_declined'):
                    return {'success': False, 'message': intent.get('message'), 'card_declined': True}
                
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
    required_fields = ['price_id', 'plan_name']
    
    if data.get('is_modification') == 'true':
        if data.get('payment_method_token'):
            required_fields.append('payment_method_token')
            
    return all([data.get(field) for field in required_fields])

def add_payment_method_to_customer(user, payment_method_token):
    try:
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}",
                metadata={"user_id": str(user.id)}
            )
            user.stripe_customer_id = customer.id
            user.save()
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)
        
        payment_method = stripe.PaymentMethod.attach(
            payment_method_token,
            customer=user.stripe_customer_id,
        )
        
        card_data = payment_method.get('card', {})
        
        existing_methods = stripe.PaymentMethod.list(
            customer=user.stripe_customer_id,
            type="card",
        )
        
        if len(existing_methods.data) == 1:
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={
                    "default_payment_method": payment_method.id
                }
            )
            is_default = True
        else:
            is_default = False
            
        return {
            "success": True,
            "payment_method_id": payment_method.id,
            "card_brand": card_data.get('brand', '').lower(),
            "last_four": card_data.get('last4', ''),
            "exp_month": card_data.get('exp_month', 0),
            "exp_year": card_data.get('exp_year', 0),
            "is_default": is_default
        }
    except stripe.error.CardError as e:
        return {
            'success': False,
            'message': str(e.user_message),
            'code': e.code
        }
    
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "message": str(e),
            "code": e.code
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "code": "unknown_error"
        }

def get_payment_methods(user):
    try:
        if not user.stripe_customer_id:
            return {"success": True, "payment_methods": []}
            
        payment_methods = stripe.PaymentMethod.list(
            customer=user.stripe_customer_id,
            type="card",
        )
        
        customer = stripe.Customer.retrieve(user.stripe_customer_id)
        default_payment_method = customer.get('invoice_settings', {}).get('default_payment_method')
        
        formatted_methods = []
        for method in payment_methods.data:
            card = method.get('card', {})
            formatted_methods.append({
                "id": method.id,
                "card_brand": card.get('brand', '').lower(),
                "last_four": card.get('last4', ''),
                "exp_month": card.get('exp_month', 0),
                "exp_year": card.get('exp_year', 0),
                "is_default": method.id == default_payment_method
            })
            
        return {
            "success": True,
            "payment_methods": formatted_methods
        }
            
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "message": str(e),
            "code": e.code
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "code": "unknown_error"
        }

def set_default_payment_method(user, payment_method_id):
    try:
        if not user.stripe_customer_id:
            return {"success": False, "message": "No customer account found"}
            
        stripe.Customer.modify(
            user.stripe_customer_id,
            invoice_settings={
                "default_payment_method": payment_method_id
            }
        )
            
        return {
            "success": True,
            "message": "Default payment method updated successfully"
        }
            
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "message": str(e),
            "code": e.code
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "code": "unknown_error"
        }

def delete_payment_method(user, payment_method_id):
    try:
        if not user.stripe_customer_id:
            return {"success": False, "message": "No customer account found"}
            
        customer = stripe.Customer.retrieve(user.stripe_customer_id)
        default_payment_method = customer.get('invoice_settings', {}).get('default_payment_method')
        
        stripe.PaymentMethod.detach(payment_method_id)
        
        if payment_method_id == default_payment_method:
            payment_methods = stripe.PaymentMethod.list(
                customer=user.stripe_customer_id,
                type="card",
            )
            
            if payment_methods.data:
                stripe.Customer.modify(
                    user.stripe_customer_id,
                    invoice_settings={
                        "default_payment_method": payment_methods.data[0].id
                    }
                )
            
        return {
            "success": True,
            "message": "Payment method deleted successfully"
        }
            
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "message": str(e),
            "code": e.code
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"An error occurred: {str(e)}",
            "code": "unknown_error"
        }