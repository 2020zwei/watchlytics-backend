from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Invoice
from .serializers import InvoiceSerializer, InvoiceDetailSerializer
from .permissions import IsOwnerOrAdmin

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'issue_date', 'due_date']
    search_fields = ['invoice_number', 'customer_info', 'notes']
    ordering_fields = ['issue_date', 'due_date', 'total', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return InvoiceDetailSerializer
        return InvoiceSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Invoice.objects.all()
        return Invoice.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = 'paid'
        invoice.paid_date = timezone.now().date()
        invoice.save()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_sent(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = 'sent'
        invoice.save()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == 'paid':
            return Response({"error": "Cannot cancel a paid invoice"},
                           status=status.HTTP_400_BAD_REQUEST)
        invoice.status = 'canceled'
        invoice.save()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)
