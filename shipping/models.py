from django.db import models
from django.utils import timezone
from transactions.models import TransactionHistory
from django.conf import settings
from auth_.models import User

class ShippingConfig(models.Model):
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='shipping_config')
    
    app_username = models.CharField(max_length=100, default='Multi_onDemand')
    app_password = models.CharField(max_length=100, default='dLCGp2kk7X7ePUMV')
    account_id = models.CharField(max_length=50, help_text="IFS Account ID (provided by IFS)")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Shipping Configuration"
        verbose_name_plural = "Shipping Configurations"
    
    def __str__(self):
        return f"IFS Config for {self.user.username} - Account {self.account_id}"
    
    def get_auth_data(self):
        """Return the complete authentication data for IFS API"""
        return {
            'AppUserName': self.app_username,
            'AppPassword': self.app_password,
            'account_id': self.account_id
        }


class SenderAddress(models.Model):
    """Stores sender address information from IFS system"""
    ifs_id = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    address1 = models.CharField(max_length=200)
    address2 = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="United States")
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_residential = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.address1}, {self.city}, {self.state}"


class RecipientAddress(models.Model):
    """Stores recipient address information"""
    ifs_id = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    label_name = models.CharField(max_length=100, blank=True, null=True)
    address1 = models.CharField(max_length=200)
    address2 = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="United States")
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_residential = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.address1}, {self.city}, {self.state}"


class Shipment(models.Model):
    """Enhanced shipping information for transactions"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('label_created', 'Label Created'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
        ('voided', 'Voided'),
    )
    
    PACKAGE_TYPE_CHOICES = (
        ('YOUR_PACKAGING', 'Your Packaging'),
        ('FEDEX_SMALL_BOX', 'FedEx Small Box S1'),
        ('FEDEX_MEDIUM_BOX', 'FedEx Medium Box M1'),
        ('FEDEX_LARGE_BOX', 'FedEx Large Box L1'),
        ('FEDEX_ENVELOPE', 'FedEx Envelope'),
    )
    
    SERVICE_TYPE_CHOICES = (
        ('FEDEX_2_DAY', '2nd Day'),
        ('FEDEX_GROUND', 'Ground'),
        ('PRIORITY_OVERNIGHT', 'Priority Overnight'),
        ('STANDARD_OVERNIGHT', 'Standard Overnight'),
        ('INTERNATIONAL_ECONOMY', 'International Economy'),
        ('INTERNATIONAL_PRIORITY', 'International Priority'),
    )
    
    PAYMENT_TYPE_CHOICES = (
        ('SENDER', 'Bill Sender (Prepaid)'),
        ('RECIPIENT', 'Bill Recipient'),
        ('THIRD_PARTY', 'Bill Third Party'),
    )
    
    SIGNATURE_TYPE_CHOICES = (
        ('NO_SIGNATURE_REQUIRED', 'No Signature Required'),
        ('DIRECT_SIGNATURE_REQUIRED', 'Direct Signature Required'),
        ('ADULT_SIGNATURE_REQUIRED', 'Adult Signature Required'),
    )
    
    LABEL_FORMAT_CHOICES = (
        ('PAPER_8.5X11_BOTTOM_HALF_LABEL', 'Office Printer (8.5 x 11) Bottom Half Label'),
        ('PAPER_8.5X11_TOP_HALF_LABEL', 'Office Printer (8.5 x 11) Top Half Label'),
        ('PAPER_LETTER', 'Office Printer Letter'),
        ('STOCK_4X6', 'Thermal Label Stock (4 X 6)'),
    )

    # Relation fields
    transaction_history = models.OneToOneField(TransactionHistory, on_delete=models.CASCADE, related_name='shipment')
    sender = models.ForeignKey(SenderAddress, on_delete=models.PROTECT, related_name='shipments_sent')
    recipient = models.ForeignKey(RecipientAddress, on_delete=models.PROTECT, related_name='shipments_received')
    
    # IFS specific fields
    ifs_shipment_id = models.CharField(max_length=100, blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    zone_id = models.CharField(max_length=20, blank=True, null=True)
    
    # Package information
    package_type = models.CharField(max_length=50, choices=PACKAGE_TYPE_CHOICES, default='FEDEX_MEDIUM_BOX')
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPE_CHOICES, default='FEDEX_GROUND')
    package_weight = models.DecimalField(max_digits=8, decimal_places=2)
    package_length = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    package_width = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    package_height = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    declared_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Shipment options
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='SENDER')
    account_number = models.CharField(max_length=50, blank=True, null=True)
    signature_type = models.CharField(max_length=50, choices=SIGNATURE_TYPE_CHOICES, default='NO_SIGNATURE_REQUIRED')
    saturday_delivery = models.BooleanField(default=False)
    hold_at_location = models.BooleanField(default=False)
    
    # Hold at location information (if applicable)
    hal_contact_person = models.CharField(max_length=100, blank=True, null=True)
    hal_company_name = models.CharField(max_length=100, blank=True, null=True)
    hal_address = models.CharField(max_length=200, blank=True, null=True)
    hal_city = models.CharField(max_length=100, blank=True, null=True)
    hal_state = models.CharField(max_length=100, blank=True, null=True)
    hal_zip_code = models.CharField(max_length=20, blank=True, null=True)
    hal_phone = models.CharField(max_length=50, blank=True, null=True)
    hal_location_property = models.CharField(max_length=200, blank=True, null=True)
    
    # Shipment dates
    pickup_date = models.DateField(default=timezone.now)
    estimated_delivery = models.DateField(blank=True, null=True)
    shipped_date = models.DateField(blank=True, null=True)
    delivered_date = models.DateField(blank=True, null=True)
    
    # Label information
    label_format = models.CharField(max_length=50, choices=LABEL_FORMAT_CHOICES, default='STOCK_4X6')
    label_url = models.URLField(blank=True, null=True)
    commercial_invoice_url = models.URLField(blank=True, null=True)
    return_label_url = models.URLField(blank=True, null=True)
    receipt_url = models.URLField(blank=True, null=True)
    
    # Shipment status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Added default value
    reference = models.CharField(max_length=100, blank=True, null=True)
    reference_on_label = models.BooleanField(default=False)
    
    # Additional information
    tracking_history = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # International shipment specific fields
    is_international = models.BooleanField(default=False)
    duties_taxes_paid_by = models.CharField(max_length=50, blank=True, null=True)
    customs_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    def __str__(self):
        return f"Shipment for {self.transaction_history.product} - {self.tracking_number or 'No Tracking'}"


class NotificationEmail(models.Model):
    """Email recipients for shipment notifications"""
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='notification_emails')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Notification for {self.email}"


class ShipmentProduct(models.Model):
    """Products included in international shipment for customs"""
    WEIGHT_UNIT_CHOICES = (
        ('LB', 'Pounds'),
        ('KG', 'Kilograms'),
    )
    
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200)
    hts_number = models.CharField(max_length=50, blank=True, null=True)
    weight_unit = models.CharField(max_length=10, choices=WEIGHT_UNIT_CHOICES, default='LB')
    quantity = models.IntegerField(default=1)
    gross_weight = models.DecimalField(max_digits=8, decimal_places=2)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    origin_country = models.CharField(max_length=100, default="United States")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.quantity} units"