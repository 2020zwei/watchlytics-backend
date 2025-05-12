from rest_framework import generics, permissions
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer, UserCardSerializer
import stripe
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from auth_.utils import CustomException
from .pagination import CustomPagination
from subscription.stripe_pay import make_stripe_order_payment, validate_stripe_fields, get_user_subscriptions_by_status, add_payment_method_to_customer, get_payment_methods, set_default_payment_method, delete_payment_method
from subscription.stripe_processor import StripeEventProcessor
from .models import UserCard
class PlanListAPIView(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CustomPagination

class PlanDetailAPIView(generics.RetrieveAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]

class UserSubscriptionAPIView(generics.RetrieveAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.subscription


class CreateSubscriptionAPIView(generics.CreateAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UpdateSubscriptionAPIView(generics.UpdateAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.subscription

class StripePayment(APIView):
    permission_classes = [IsAuthenticated]

    def cancel_subscription(self, user):
        try:
            subscription = Subscription.objects.filter(user=user, is_active=True).first()
            
            if not subscription:
                raise CustomException("Subscription not found")

            if subscription.plan.name == 'FREE' or not subscription.stripe_subscription_id:
                
                subscription.is_active = False
                subscription.status = 'canceled'
                subscription.save()
            else:
                response = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                    metadata={"is_cancelled": True}
                )
                
            return True
            
        except Exception as e:
            raise CustomException({"message": str(e)})

    def modify_subscription(self, user, new_price_id):
        try:
            subscription = Subscription.objects.filter(user=user, is_active=True).first()
            
            if not subscription:
                raise CustomException("Subscription not found")
            
            if new_price_id == 'FREE' or new_price_id.upper() == 'FREE':
                if subscription.stripe_subscription_id:
                    try:
                        stripe.Subscription.delete(subscription.stripe_subscription_id)
                    except Exception as e:
                        print(f"Error cancelling Stripe subscription: {str(e)}")
                
                plan = Plan.objects.get(name='FREE')
                
                subscription.plan = plan
                subscription.stripe_subscription_id = None
                subscription.start_date = timezone.now()
                subscription.end_date = timezone.now() + timedelta(days=30)
                subscription.status = 'active'
                subscription.save()
                
                return True
            
            if subscription.plan.name == 'FREE' or not subscription.stripe_subscription_id:
                
                # Mark FREE plan as inactive
                subscription.is_active = False
                subscription.status = 'canceled'
                subscription.save()
                
                # The regular subscription creation flow will handle the rest
                return False
            
            # Regular paid plan modification
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            subscription_item_id = stripe_subscription['items']['data'][0]['id']
            
            response = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
                proration_behavior="always_invoice",
                items=[{
                    "id": subscription_item_id,
                    "price": new_price_id
                }],
                metadata={"price_id": new_price_id, "is_upgrade": True}
            )
            
            new_plan = None
            plans = Plan.objects.all()
            for plan in plans:
                if plan.stripe_price_id == new_price_id:
                    new_plan = plan
                    break
                    
            if not new_plan:
                raise CustomException(f"No plan found for price ID: {new_price_id}")
                
            subscription.plan = new_plan
            subscription.status = 'active'
            current_date = timezone.now()
            subscription.start_date = current_date
            if new_plan.name == 'PRO':
                subscription.end_date = current_date + timedelta(days=365)
            else:
                subscription.end_date = current_date + timedelta(days=30)
            subscription.save()
            
            return True
        except Exception as e:
            raise CustomException(str(e))

    def cancel_subscription_flow(self, user):
        subscription = Subscription.objects.filter(user=user, is_active=True).first()
        
        if subscription:
            self.cancel_subscription(user)
            response = {
                'success': True,
                'message': 'Success! Your subscription will remain active until the current period ends.'
            }
            return Response(response, status.HTTP_200_OK)
        else:
            response = {'success': False, 'message': "We did not find any active subscription."}
            return Response(response, status.HTTP_400_BAD_REQUEST)

    def apply_free_plan(self, user):
        """Apply free plan subscription without requiring payment information"""
        try:
            # Check if user already has an active subscription
            existing_subscription = Subscription.objects.filter(
                user=user
            ).first()
            
            free_plan = Plan.objects.filter(name='FREE').first()
            if not free_plan:
                return Response({
                    'success': False,
                    'message': 'FREE plan not found in the system.'
                }, status.HTTP_400_BAD_REQUEST)
            
            if existing_subscription:
                if existing_subscription.is_active and existing_subscription.plan.name == 'FREE':
                    return Response({
                        'success': False,
                        'message': 'You are already on the FREE plan.'
                    }, status.HTTP_400_BAD_REQUEST)
                
                if existing_subscription.stripe_subscription_id:
                    try:
                        stripe.Subscription.delete(existing_subscription.stripe_subscription_id)
                    except Exception as e:
                        print(f"Error cancelling Stripe subscription: {str(e)}")
                
                # Update the existing subscription to FREE plan
                start_date = timezone.now()
                end_date = start_date + timedelta(days=30)  # FREE plan valid for 30 days
                
                existing_subscription.plan = free_plan
                existing_subscription.stripe_subscription_id = None
                existing_subscription.status = 'active'
                existing_subscription.start_date = start_date
                existing_subscription.end_date = end_date
                existing_subscription.is_active = True
                existing_subscription.save()
                
                return Response({
                    'success': True,
                    'message': 'FREE plan has been successfully activated.'
                }, status.HTTP_200_OK)
            else:
                # If no subscription exists at all, create a new one
                start_date = timezone.now()
                end_date = start_date + timedelta(days=30)  # FREE plan valid for 30 days
                
                Subscription.objects.create(
                    user=user,
                    plan=free_plan,
                    stripe_subscription_id=None,
                    status='active',
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
                
                return Response({
                    'success': True,
                    'message': 'FREE plan has been successfully activated.'
                }, status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Unable to apply FREE plan: {str(e)}'
            }, status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        try:
            user = request.user
            plan_name = request.data.get('plan_name', '')
            price_id = request.data.get('price_id', '')
            
            if request.data.get('is_cancelled_subscription', "false").lower() == "true":
                return self.cancel_subscription_flow(user=user)
            
            if plan_name.upper() == 'FREE':
                return self.apply_free_plan(user)

            existing_subscription = Subscription.objects.filter(user=user).first()
            
            if existing_subscription and existing_subscription.is_active:
                if existing_subscription.plan.name.upper() == plan_name.upper():
                    message = f"You already have an active {plan_name} plan subscription."
                    response = {'success': False, 'message': message, 'is_duplicate': True}
                    return Response(response, status.HTTP_400_BAD_REQUEST)
                
                if hasattr(existing_subscription.plan, 'stripe_price_id') and existing_subscription.plan.stripe_price_id == price_id:
                    message = f"You are already subscribed to this plan. Please choose a different plan to upgrade or downgrade."
                    response = {'success': False, 'message': message, 'is_duplicate': True}
                    return Response(response, status.HTTP_400_BAD_REQUEST)

            # Validate required fields for paid plans
            required_fields = validate_stripe_fields(request.data)
            if not required_fields:
                response = {'success': False, 'message': "Some Payment Fields are missing"}
                return Response(response, status.HTTP_400_BAD_REQUEST)

            plan = Plan.objects.filter(name__iexact=plan_name).first()
            if not plan:
                message = "Plan not found."
                response = {'success': False, 'message': message}
                return Response(response, status.HTTP_400_BAD_REQUEST)

            # If user has an existing subscription, modify it
            if existing_subscription:
                if existing_subscription.is_active:
                    try:
                        get_response_data = self.modify_subscription(user, price_id)
                        if get_response_data is False:
                            message = 'Problem with your plan change. Please contact customer support or try again after logout.'
                            response = {'success': False, 'message': message, 'card_declined': False}
                            return Response(response, status.HTTP_400_BAD_REQUEST)
                        else:
                            return Response({'success': True, 'message': "Subscription updated successfully"}, status.HTTP_200_OK)
                    except Exception as modify_error:
                        message = f'Problem with your plan change: {str(modify_error)}'
                        response = {'success': False, 'message': message, 'card_declined': 'card declined' in str(modify_error).lower()}
                        return Response(response, status.HTTP_400_BAD_REQUEST)
                else:
                    existing_subscription.plan = plan
                    existing_subscription.stripe_subscription_id = None  # Will be updated after payment processing
                    existing_subscription.is_active = True
                    existing_subscription.status = 'active'
                    existing_subscription.start_date = timezone.now()
                    existing_subscription.end_date = timezone.now() + timedelta(days=30 if plan.name != 'PRO' else 365)
            
            active_subscriptions = get_user_subscriptions_by_status(user, 'active')
            if active_subscriptions and active_subscriptions.get('data', []):
                message = "You already have an active subscription. Please cancel that first."
                response = {'success': False, 'message': message}
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            incomplete_subscriptions = get_user_subscriptions_by_status(user, 'incomplete')
            if incomplete_subscriptions and incomplete_subscriptions.get('data', []):
                message = "You have an incomplete subscription. Please update your payment method."
                response = {'success': False, 'message': message}
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            payment_intent = make_stripe_order_payment({
                'payment_method_token': request.data.get('payment_method_token'),
                'price_id': price_id,
                'user_id': str(request.user.id),
            })

            if not payment_intent['success']:
                response = {
                    'success': False,
                    'message': payment_intent['message'],
                    'card_declined': payment_intent.get('card_declined', False)
                }
                return Response(response, status.HTTP_400_BAD_REQUEST)
            
            if existing_subscription:
                existing_subscription.plan = plan
                existing_subscription.stripe_subscription_id = payment_intent['stripe_subscription_id']
                existing_subscription.status = 'active'
                existing_subscription.start_date = timezone.now()
                existing_subscription.end_date = timezone.now() + timedelta(days=30 if plan.name != 'PRO' else 365)
                existing_subscription.is_active = True
                existing_subscription.save()
            else:
                start_date = timezone.now()
                end_date = start_date + timedelta(days=30 if plan.name != 'PRO' else 365)
                
                Subscription.objects.create(
                    user=user,
                    plan=plan,
                    stripe_subscription_id=payment_intent['stripe_subscription_id'],
                    status='active',
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )

            response = {'success': True, 'message': payment_intent['message']}
            return Response(response, status.HTTP_200_OK)

        except Exception as e:
            response = {
                'success': False, 
                'message': f'Unable to process the payment: {str(e)}',
                'card_declined': 'card' in str(e).lower() and 'declined' in str(e).lower()
            }
            return Response(response, status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        try:
            plans = Plan.objects.all().order_by('id')

            if plans:
                serializer = PlanSerializer(plans, many=True)
                return Response(status=status.HTTP_200_OK, data=serializer.data)
            else:
                response = {
                    'success': False,
                    'message': 'Unable to get the price id'
                }
                return Response(response, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            response = {
                'success': False,
                'message': 'Unable to get the price id'
            }
            return Response(response, status.HTTP_400_BAD_REQUEST)


class StripeWebhook(APIView):
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request):
        try:
            processor = StripeEventProcessor(request.data)

            details = processor.event_process()
            if details.status_code == int(200):
                return Response(data=details.data, status=status.HTTP_200_OK)
                
            if details.status_code == int(400):
                return Response(data=details.data, status=status.HTTP_400_BAD_REQUEST)

            return Response(data={'data': details, 'success': True, 'error': {}})

        except Exception as e:
            if type(e) is CustomException:
                raise e
            message = f"An error occurred: {str(e)}"
            return message


class GetSubscriptionDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Get details of user's current subscription plan"""
        try:
            subscription = Subscription.objects.filter(
                user=request.user, 
                is_active=True
            ).order_by('-start_date').first()

            if subscription:
                # Determine billing period
                if subscription.plan.name == 'PRO':
                    billing_period = 'Monthly'
                elif subscription.plan.name == 'BASIC' or subscription.plan.name == 'ADVANCED':  
                    billing_period = 'Monthly'
                else:
                    billing_period = 'Free'
                
                # Check if subscription is set to cancel
                is_cancelling = False
                if subscription.stripe_subscription_id:
                    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                    is_cancelling = stripe_sub.get('cancel_at_period_end', False)
                
                data = {
                    'id': subscription.id,
                    'current_subscription': subscription.plan.name,
                    'is_cancel_subscription': is_cancelling,
                    'price': subscription.plan.price,
                    'billing_period': billing_period,
                    'features': subscription.plan.description,
                    'start_date': subscription.start_date.strftime("%d %B, %Y"),
                    'end_date': subscription.end_date.strftime("%d %B, %Y"),
                    'status': subscription.status,
                }
            else:
                data = {
                    'current_subscription': None,
                    'is_cancel_subscription': False,
                    'price': None,
                    'billing_period': None,
                    'features': [],
                    'start_date': None,
                    'end_date': None,
                }

            response = {
                'success': True,
                'plan': data
            }
            return Response(response, status.HTTP_200_OK)
        except Exception as e:
            response = {
                'success': False,
                'message': f'Something went wrong: {str(e)}'
            }
            return Response(response, status.HTTP_400_BAD_REQUEST)
        

class CardManagementAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        payment_method_token = request.data.get('payment_method_token')
        
        if not payment_method_token:
            return Response({
                'success': False, 
                'message': 'Payment method token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        result = add_payment_method_to_customer(request.user, payment_method_token)
        
        if not result.get('success', False):
            return Response({
                'success': False,
                'message': result.get('message', 'Failed to add payment method'),
                'card_declined': 'card_declined' in result.get('code', '')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        card = UserCard.objects.create(
            user=request.user,
            stripe_payment_method_id=result['payment_method_id'],
            card_brand=result['card_brand'],
            last_four=result['last_four'],
            exp_month=result['exp_month'],
            exp_year=result['exp_year'],
            is_default=result['is_default']
        )
        
        serializer = UserCardSerializer(card)
        
        return Response({
            'success': True,
            'message': 'Payment method added successfully',
            'card': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def get(self, request):
        cards = UserCard.objects.filter(user=request.user).order_by('-is_default', '-created_at')
        serializer = UserCardSerializer(cards, many=True)
        
        return Response({
            'success': True,
            'cards': serializer.data
        }, status=status.HTTP_200_OK)

class CardOperationsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, card_id):
        try:
            card = UserCard.objects.get(id=card_id, user=request.user)
        except UserCard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Card not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        result = set_default_payment_method(request.user, card.stripe_payment_method_id)
        
        if not result.get('success', False):
            return Response({
                'success': False,
                'message': result.get('message', 'Failed to set default payment method')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        UserCard.objects.filter(user=request.user).update(is_default=False)
        card.is_default = True
        card.save()
        
        serializer = UserCardSerializer(card)
        
        return Response({
            'success': True,
            'message': 'Default payment method updated successfully',
            'card': serializer.data
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, card_id):
        try:
            card = UserCard.objects.get(id=card_id, user=request.user)
        except UserCard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Card not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        result = delete_payment_method(request.user, card.stripe_payment_method_id)
        
        if not result.get('success', False):
            return Response({
                'success': False,
                'message': result.get('message', 'Failed to delete payment method')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if card.is_default:
            next_card = UserCard.objects.filter(user=request.user).exclude(id=card.id).order_by('-created_at').first()
            if next_card:
                next_card.is_default = True
                next_card.save()
        
        card.delete()
        
        return Response({
            'success': True,
            'message': 'Payment method deleted successfully'
        }, status=status.HTTP_200_OK)