from django.shortcuts import render
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import serializers
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
from .serializers import CustomAuthTokenSerializer 
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework import status, permissions
from django.db import IntegrityError
from rest_framework import status
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_decode
from django.shortcuts import redirect
import os
from .serializers import (
    ForgotPasswordSerializer, 
    PasswordResetConfirmSerializer,
    UserUpdateSerializer,
)


User = get_user_model()

class SignUpView(CreateAPIView):
    throttle_classes = [AnonRateThrottle]
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        return Response(
            {'access_token': str(access_token), 'user': serializer.data},
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def perform_create(self, serializer):
        user = serializer.save()
        verification_url = self.generate_verification_url(user)
        email_subject = "Verify your email"
        email_message = render_to_string(
            "email/verification_email.html", 
            {
                "user": user, 
                "verification_url": verification_url
            }
        )

        send_mail(
            subject=email_subject,
            message=email_message,
            from_email="info@once-more.com",
            recipient_list=[user.email],
            fail_silently=False
        )
        return user

    def generate_verification_url(self, user):
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        verification_url = f"{self.request.build_absolute_uri('/api/auth/verify-email/')}{uidb64}/{token}/"
        return verification_url

class CustomAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = get_user_model().objects.filter(email=email).first()

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_email_verified:
            raise serializers.ValidationError("Email not verified. Please verify your email before logging in.")

        if user and user.check_password(password):
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Invalid credentials")
        
        return attrs

class SignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = CustomAuthTokenSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Create JWT token
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            return Response({
                'access_token': str(access_token),
                'refresh_token': str(refresh),
                'user_id': user.id,
                'email': user.email,
                'is_subscribed': hasattr(user, 'subscription') and user.subscription is not None
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ProfileView(APIView):
    permission_classes=[IsAuthenticated]
    serializer_class=UserSerializer
    # throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def get(self, request, *args, **kwargs):
        try:
            profile = User.objects.filter(id=request.user.id).first()
            
            if not profile:
                return Response(
                    {
                        'message': 'User profile not found'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
                
            serializers = UserSerializer(profile)
            return Response(
                {
                    'message': "Profile retrieved successfully",
                    'data': serializers.data,
                    'is_subscribed': hasattr(profile, 'subscription') and profile.subscription is not None,
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'message': f'An error occurred: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uid, token):
        serializer = PasswordResetConfirmSerializer(
            data=request.data, context={"uid": uid, "token": token}
        )
        if serializer.is_valid():
            return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return redirect(f"{os.getenv('ORIGIN_URL', '')}")

        if default_token_generator.check_token(user, token):
            user.is_email_verified = True
            user.save()
            return redirect(f"{os.getenv('ORIGIN_URL', '')}")
        else:
            return redirect(f"{os.getenv('ORIGIN_URL', '')}")
        

class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")
        if password != confirm_password:
            return Response(
                    {
                        'password': ['Passwords do not match']
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
        user = User.objects.get(id=request.user.id)

        if password and user.check_password(password):
            return Response(
                {
                    'password': ['New password cannot be the same as the current password']
                },
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully', 'user': serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(serializers.Serializer):
        password = serializers.CharField(
            style={'input_type': 'password'},
            write_only=True,
            required=True
        )
        
        def validate_password(self, value):
            user = self.context.get('request').user
            if not user.check_password(value):
                raise serializers.ValidationError("Incorrect password. Please enter your current password to confirm account deletion.")
            return value
    
    def post(self, request):
        serializer = self.InputSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            user = request.user
            
            try:
                # Delete the user
                user.delete()
                return Response(
                    {"message": "Your account has been successfully deleted."},
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {"error": f"Failed to delete account: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)