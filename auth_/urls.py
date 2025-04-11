from django.urls import path
from .views import SignUpView, SignInView, ProfileView,  ForgotPasswordView, PasswordResetConfirmView, VerifyEmailView, UpdateProfileView, DeleteUserView

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('signin/', SignInView.as_view(), name='signin'),
    path('me/', ProfileView.as_view(), name='me'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('password-reset-confirm/<str:uid>/<str:token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-email/<str:uidb64>/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('update/', UpdateProfileView.as_view(), name='update-profile'),
    path('delete-account/', DeleteUserView.as_view(), name='delete-account'),
]
