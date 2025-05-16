from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Invoice
from .serializers import InvoiceSerializer, InvoiceDetailSerializer, InvoiceCreateSerializer
import uuid
from datetime import timedelta


class InvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InvoiceDetailSerializer
        elif self.action == 'create':
            return InvoiceCreateSerializer
        return self.serializer_class
        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_id = request.user.id
        timestamp = timezone.now().strftime('%y%m%d')
        random_string = uuid.uuid4().hex[:4].upper()
        invoice_number = f"INV-{user_id}-{timestamp}-{random_string}"
        
        serializer.validated_data['invoice_number'] = invoice_number
        serializer.validated_data['user'] = request.user
        
        if 'due_date' not in serializer.validated_data:
            issue_date = serializer.validated_data.get('issue_date', timezone.now().date())
            serializer.validated_data['due_date'] = issue_date + timedelta(days=30)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = 'paid'
        invoice.paid_date = timezone.now().date()
        invoice.save()
        
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_invoice(self, request, pk=None):
        invoice = self.get_object()
        invoice.status = 'sent'
        invoice.save()
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        queryset = self.get_queryset()
        
        total_invoices = queryset.count()
        paid_invoices = queryset.filter(status='paid').count()
        overdue_invoices = queryset.filter(status='overdue').count()
        total_revenue = sum(invoice.total for invoice in queryset.filter(status='paid'))
        pending_revenue = sum(invoice.total for invoice in queryset.filter(status__in=['sent', 'draft']))
        
        data = {
            'total_invoices': total_invoices,
            'paid_invoices': paid_invoices,
            'overdue_invoices': overdue_invoices,
            'total_revenue': total_revenue,
            'pending_revenue': pending_revenue
        }
        
        return Response(data)