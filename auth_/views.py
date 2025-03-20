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
from rest_framework.views import APIView
from rest_framework import status, permissions
from django.db import IntegrityError
from rest_framework import status
from django.utils.http import urlsafe_base64_decode
from .serializers import (
    ForgotPasswordSerializer, 
    PasswordResetConfirmSerializer,
)


User = get_user_model()

class SignUpView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

class CustomAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        # Authenticate user using email instead of username
        user = get_user_model().objects.filter(email=email).first()

        if user and user.check_password(password):
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Invalid credentials")
        
        return attrs

class SignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = CustomAuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Create JWT token
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        return Response({
            'access_token': str(access_token),
            'refresh_token': str(refresh),
            'user_id': user.id,
            'email': user.email
        }, status=status.HTTP_200_OK)
    
class ProfileView(APIView):
    permission_classes=[IsAuthenticated]
    serializer_class=UserSerializer

    def get(self, request, *args, **kwargs):
        try:
            user=request.user
            profile=User.objects.filter(id=user.id).first()
            serializers=UserSerializer(profile)
            return Response(
                {
                   'message': "Profile retreive successfully",
                    'data': serializers.data,

                }
            )
        except Exception as e:
            return Response({
                'message': str(e)
            })

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            return Response({"message": "Password reset email sent successfully."},
                            status=status.HTTP_200_OK)
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
