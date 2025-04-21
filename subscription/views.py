from rest_framework import generics, permissions
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer
import stripe
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from auth_.utils import CustomException
from subscription.stripe_pay import make_stripe_order_payment, validate_stripe_fields, get_user_subscriptions_by_status
from subscription.stripe_processor import StripeEventProcessor
from .pagination import CustomPagination
from django.db.models import Case, When, Value, IntegerField

class PlanListAPIView(generics.ListAPIView):
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CustomPagination 
    
    def get_queryset(self):
        return Plan.objects.annotate(
            custom_order=Case(
                When(name='FREE', then=Value(1)),
                When(name='BASIC', then=Value(2)),
                When(name='ADVANCED', then=Value(3)),
                When(name='PRO', then=Value(4)),
                default=Value(5),
                output_field=IntegerField()
            )
        ).order_by('custom_order')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response


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
            
            if not subscription or not subscription.stripe_subscription_id:
                raise CustomException("Subscription not found")

            if subscription.plan.name == 'FREE':
                response = stripe.Subscription.delete(subscription.stripe_subscription_id)
                
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

    def modify_subscription(self, user, new_plan_id):
        try:
            subscription = Subscription.objects.filter(user=user, is_active=True).first()
            
            if not subscription or not subscription.stripe_subscription_id:
                raise CustomException("Subscription not found")
                
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            subscription_item_id = stripe_subscription['items']['data'][0]['id']
            
            response = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
                proration_behavior="always_invoice",
                items=[{
                    "id": subscription_item_id,
                    "price": new_plan_id
                }],
                metadata={"price_id": new_plan_id, "is_upgrade": True}
            )
            
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

    def post(self, request, *args, **kwargs):

        try:
            user = request.user
            
            if request.data.get('is_cancelled_subscription', "false").lower() == "true":
                return self.cancel_subscription_flow(user=user)

            if not validate_stripe_fields(request.data):
                response = {'success': False, 'message': "Some Payment Fields are missing"}
                return Response(response, status.HTTP_400_BAD_REQUEST)

            plan_name = request.data['plan_name']
            price_id = request.data['price_id']

            plan = Plan.objects.filter(name__iexact=plan_name).first()
            if not plan:
                message = "Plan not found."
                response = {'success': False, 'message': message}
                return Response(response, status.HTTP_400_BAD_REQUEST)

            existing_subscription = Subscription.objects.filter(
                user=user, 
                is_active=True
            ).first()

            if existing_subscription and existing_subscription.plan.name == plan_name:
                message = f"You are already using {plan_name} plan. Please cancel it or upgrade to a different plan."
                response = {'success': False, 'message': message}
                return Response(response, status.HTTP_400_BAD_REQUEST)

            if existing_subscription:
                get_response_data = self.modify_subscription(user, price_id)
                if get_response_data is False:
                    message = 'Problem with your plan change. Please contact customer support or try again after logout.'
                    response = {'success': False, 'message': message}
                    
                    return Response(response, status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'success': True, 'message': "Subscription updated successfully"},
                                   status.HTTP_200_OK)
            else:
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
                    'price_id': request.data['price_id'],
                    'user_id': str(request.user.id),
                })

                if not payment_intent['success']:
                    response = {'success': False, 'message': payment_intent['message']}
                    return Response(response, status.HTTP_400_BAD_REQUEST)
                
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
            response = {'success': False, 'message': f'Unable to process the payment: {str(e)}'}
            return Response(response, status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        try:
            plans = Plan.objects.exclude(name='FREE').order_by('id')

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
                    billing_period = 'Yearly'
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
                    'current_subscription': subscription.plan.name,
                    'is_cancel_subscription': is_cancelling,
                    'price': subscription.plan.price,
                    'billing_period': billing_period,
                    'features': subscription.plan.features,
                    'start_date': subscription.start_date,
                    'end_date': subscription.end_date,
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
                'data': data
            }
            return Response(response, status.HTTP_200_OK)
        except Exception as e:
            response = {
                'success': False,
                'message': f'Something went wrong: {str(e)}'
            }
            return Response(response, status.HTTP_400_BAD_REQUEST)