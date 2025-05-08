from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import serializers
from django.utils.encoding import force_bytes, force_str
import os

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    date_joined = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'profile_picture', 'client_id', 'phone_number', 'date_joined', 'cover_picture', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'validators': []},
        }

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
    
    def get_date_joined(self, obj):
        return obj.date_joined.strftime("%d %B, %Y")

    def validate_email(self, value):
        user_qs = User.objects.filter(email=value)
        if self.instance:
            user_qs = user_qs.exclude(pk=self.instance.pk)
        if user_qs.exists():
            raise serializers.ValidationError("An account with this email already exists. Please log in or use a different email.")
        return value
class CustomAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = User.objects.filter(email=email).first()
        if user and user.check_password(password):
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Invalid credentials")
        
        return attrs

class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        uid = self.context.get("uid")
        token = self.context.get("token")

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError("Invalid token.")

        if not PasswordResetTokenGenerator().check_token(user, token):
            raise serializers.ValidationError("Invalid token.")
        
        if user.check_password(data["password"]):
            raise serializers.ValidationError({"password": "New password cannot be the same as the current password."})
        user.set_password(data["password"])
        user.save()
        return {"message": "Password updated successfully"}


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if not data.get("current_password"):
            raise serializers.ValidationError("Current password is required.")
        if not data.get("new_password"):
            raise serializers.ValidationError("New password is required.")
        
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, data):
        user = get_user_model().objects.filter(email=data["email"]).first()
        if not user:
            raise serializers.ValidationError("No user found with this email.")

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.id))

        reset_url = self.generate_reset_url(uid, token)
        self.send_password_reset_email(user, reset_url)

        return {"message": "Password reset email sent successfully"}

    def generate_reset_url(self, uid, token):
        # reset_url = f"{self.context['request'].build_absolute_uri('/reset-password/')}{uid}/{token}/"
        reset_url = f"{os.getenv('RESET_URL', '')}link={uid}/{token}/"
        return reset_url

    def send_password_reset_email(self, user, reset_url):
        email_subject = "Reset your password"
        email_message = render_to_string(
            "email/password_reset_email.html",
            {
                "user": user,
                "reset_url": reset_url,
            }
        )

        send_mail(
            subject=email_subject,
            message=email_message,
            from_email="info@once-more.com",
            recipient_list=[user.email],
            fail_silently=False
        )

class UserUpdateSerializer(serializers.ModelSerializer):
    profile_picture=serializers.ImageField(required=False)
    cover_picture=serializers.ImageField(required=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    confirm_password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'profile_picture', 'phone_number',
            'company_name', 'address', 'user_type', 'cover_picture',
            'client_id', 'password', 'confirm_password'
        ]

    def validate(self, data):
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        print("Password fields:", password, confirm_password)

        if password and password != confirm_password:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('confirm_password', None)
        print("Update called with:", validated_data)

        instance = super().update(instance, validated_data)

        if password:
            instance.set_password(password)
            instance.save()
            print("Password updated!")
        return instance
