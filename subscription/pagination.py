from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class CustomPagination(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        user = self.request.user
        current_plan = ""
        if hasattr(user, 'subscription') and user.subscription and hasattr(user.subscription, 'plan'):
            current_plan = user.subscription.plan.name
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'current_plan': current_plan,
            'has_card': user.cards.filter(is_default=True).exists(),
            'plans': data,
        })
