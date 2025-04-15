from rest_framework import generics, permissions
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer

class PlanListAPIView(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


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
