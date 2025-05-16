from datetime import datetime
from django.utils import timezone
from django.db import transaction
from .models import Invoice
from transactions.models import TransactionHistory
import uuid

class InvoiceService:
    @staticmethod
    def generate_invoice_number():
        prefix = "INV"
        year = str(datetime.now().year)
        random_part = uuid.uuid4().hex[:6].upper()
        return f"{prefix}-{year}-{random_part}"
    
    @staticmethod
    @transaction.atomic
    def create_invoice_from_transaction(transaction_id, user, **kwargs):
        try:
            transaction = TransactionHistory.objects.get(id=transaction_id)
            
            issue_date = kwargs.get('issue_date', timezone.now().date())
            due_date = kwargs.get('due_date', issue_date + timezone.timedelta(days=30))
            tax_rate = kwargs.get('tax_rate', 0)
            subtotal = transaction.amount
            tax_amount = subtotal * (tax_rate / 100)
            total = subtotal + tax_amount
            
            invoice_number = kwargs.get('invoice_number', InvoiceService.generate_invoice_number())
            
            invoice = Invoice.objects.create(
                user=user,
                transaction_history=transaction,
                invoice_number=invoice_number,
                status='draft',
                issue_date=issue_date,
                due_date=due_date,
                subtotal=subtotal,
                tax_amount=tax_amount,
                tax_rate=tax_rate,
                total=total,
                notes=kwargs.get('notes', ''),
                terms=kwargs.get('terms', ''),
                company_info=kwargs.get('company_info', {}),
                customer_info=kwargs.get('customer_info', {})
            )
            
            return invoice
            
        except TransactionHistory.DoesNotExist:
            raise ValueError(f"Transaction with ID {transaction_id} does not exist")
    
    @staticmethod
    def check_overdue_invoices():
        today = timezone.now().date()
        overdue_invoices = Invoice.objects.filter(
            status='sent',
            due_date__lt=today
        )
        
        count = overdue_invoices.update(status='overdue')
        return count