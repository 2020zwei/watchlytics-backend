from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from .managers import UserManager
import uuid
from django.conf import settings
from django.core.validators import FileExtensionValidator,  RegexValidator
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

import os

def get_profile_image_path(instance, filename):
    ext = filename.split('.')[-1]
    user_id = instance.pk or uuid.uuid4().hex
    return f'profile_pictures/user_{user_id}/profile.{ext}'

def validate_name(value):
    if value and value.isdigit():
        raise ValidationError("Name cannot consist of only numbers.")

def validate_password(value):
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in value):
        raise ValidationError("Password must contain at least one number.")
    if not any(char.isalpha() for char in value):
        raise ValidationError("Password must contain at least one letter.")

class User(AbstractUser):

    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('trader', 'Trader'),
        ('accountant', 'Accountant'),
        ('analyst', 'Analyst'),
    )
    
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(
        max_length=30,
        blank=True, 
        null=True,
        validators=[validate_name]
    )
    last_name = models.CharField(
        max_length=30,
        blank=True, 
        null=True,
        validators=[validate_name]
    )
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        storage=default_storage
    )
    cover_picture = models.ImageField(
        upload_to="cover_pictures/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        storage=default_storage
    )
    client_id = models.CharField(
        max_length=10,
        validators=[RegexValidator(r'^\d{8,10}$', message="Client ID must be 8 to 10 digits")],
        blank=True,
        null=True
    )
    is_admin = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='trader')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    password = models.CharField(
        max_length=128,
        validators=[validate_password]
        )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UserManager()
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

class PasswordReset(models.Model):
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_used = models.BooleanField(default=False)
    expiry_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.token}"
    
    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and self.expiry_date > timezone.now()