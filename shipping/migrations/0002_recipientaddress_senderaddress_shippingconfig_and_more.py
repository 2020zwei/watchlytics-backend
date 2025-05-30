# Generated by Django 4.2.7 on 2025-05-21 12:44

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('shipping', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecipientAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ifs_id', models.CharField(blank=True, max_length=50, null=True)),
                ('name', models.CharField(max_length=100)),
                ('company_name', models.CharField(blank=True, max_length=100, null=True)),
                ('label_name', models.CharField(blank=True, max_length=100, null=True)),
                ('address1', models.CharField(max_length=200)),
                ('address2', models.CharField(blank=True, max_length=200, null=True)),
                ('city', models.CharField(max_length=100)),
                ('state', models.CharField(max_length=100)),
                ('zip_code', models.CharField(max_length=20)),
                ('country', models.CharField(default='United States', max_length=100)),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('is_residential', models.BooleanField(default=False)),
                ('is_verified', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='SenderAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ifs_id', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('company_name', models.CharField(blank=True, max_length=100, null=True)),
                ('address1', models.CharField(max_length=200)),
                ('address2', models.CharField(blank=True, max_length=200, null=True)),
                ('city', models.CharField(max_length=100)),
                ('state', models.CharField(max_length=100)),
                ('zip_code', models.CharField(max_length=20)),
                ('country', models.CharField(default='United States', max_length=100)),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('is_residential', models.BooleanField(default=False)),
                ('is_primary', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='ShippingConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('auth_key', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Shipping Configuration',
                'verbose_name_plural': 'Shipping Configurations',
            },
        ),
        migrations.RemoveField(
            model_name='shipment',
            name='carrier',
        ),
        migrations.RemoveField(
            model_name='shipment',
            name='shipping_address',
        ),
        migrations.RemoveField(
            model_name='shipment',
            name='shipping_method',
        ),
        migrations.AddField(
            model_name='shipment',
            name='account_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='commercial_invoice_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='customs_value',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='declared_value',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='shipment',
            name='duties_taxes_paid_by',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_address',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_city',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_company_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_contact_person',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_location_property',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_phone',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_state',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hal_zip_code',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='hold_at_location',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='shipment',
            name='ifs_shipment_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='is_international',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='shipment',
            name='label_format',
            field=models.CharField(choices=[('PAPER_8.5X11_BOTTOM_HALF_LABEL', 'Office Printer (8.5 x 11) Bottom Half Label'), ('PAPER_8.5X11_TOP_HALF_LABEL', 'Office Printer (8.5 x 11) Top Half Label'), ('PAPER_LETTER', 'Office Printer Letter'), ('STOCK_4X6', 'Thermal Label Stock (4 X 6)')], default='STOCK_4X6', max_length=50),
        ),
        migrations.AddField(
            model_name='shipment',
            name='package_height',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='package_length',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='package_type',
            field=models.CharField(choices=[('YOUR_PACKAGING', 'Your Packaging'), ('FEDEX_SMALL_BOX', 'FedEx Small Box S1'), ('FEDEX_MEDIUM_BOX', 'FedEx Medium Box M1'), ('FEDEX_LARGE_BOX', 'FedEx Large Box L1'), ('FEDEX_ENVELOPE', 'FedEx Envelope')], default='FEDEX_MEDIUM_BOX', max_length=50),
        ),
        migrations.AddField(
            model_name='shipment',
            name='package_weight',
            field=models.DecimalField(decimal_places=2, default=1, max_digits=8),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='shipment',
            name='package_width',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='payment_type',
            field=models.CharField(choices=[('SENDER', 'Bill Sender (Prepaid)'), ('RECIPIENT', 'Bill Recipient'), ('THIRD_PARTY', 'Bill Third Party')], default='SENDER', max_length=20),
        ),
        migrations.AddField(
            model_name='shipment',
            name='pickup_date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='shipment',
            name='receipt_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='reference',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='reference_on_label',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='shipment',
            name='return_label_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='shipment',
            name='saturday_delivery',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='shipment',
            name='service_type',
            field=models.CharField(choices=[('FEDEX_2_DAY', '2nd Day'), ('FEDEX_GROUND', 'Ground'), ('PRIORITY_OVERNIGHT', 'Priority Overnight'), ('STANDARD_OVERNIGHT', 'Standard Overnight'), ('INTERNATIONAL_ECONOMY', 'International Economy'), ('INTERNATIONAL_PRIORITY', 'International Priority')], default='FEDEX_GROUND', max_length=50),
        ),
        migrations.AddField(
            model_name='shipment',
            name='signature_type',
            field=models.CharField(choices=[('NO_SIGNATURE_REQUIRED', 'No Signature Required'), ('DIRECT_SIGNATURE_REQUIRED', 'Direct Signature Required'), ('ADULT_SIGNATURE_REQUIRED', 'Adult Signature Required')], default='NO_SIGNATURE_REQUIRED', max_length=50),
        ),
        migrations.AddField(
            model_name='shipment',
            name='zone_id',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='shipment',
            name='shipping_cost',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name='shipment',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('label_created', 'Label Created'), ('in_transit', 'In Transit'), ('delivered', 'Delivered'), ('returned', 'Returned'), ('voided', 'Voided')], default='pending', max_length=20),
        ),
        migrations.CreateModel(
            name='ShipmentProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.CharField(max_length=200)),
                ('hts_number', models.CharField(blank=True, max_length=50, null=True)),
                ('weight_unit', models.CharField(choices=[('LB', 'Pounds'), ('KG', 'Kilograms')], default='LB', max_length=10)),
                ('quantity', models.IntegerField(default=1)),
                ('gross_weight', models.DecimalField(decimal_places=2, max_digits=8)),
                ('value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('origin_country', models.CharField(default='United States', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('shipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='shipping.shipment')),
            ],
        ),
        migrations.CreateModel(
            name='NotificationEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('message', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('shipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_emails', to='shipping.shipment')),
            ],
        ),
        migrations.AddField(
            model_name='shipment',
            name='recipient',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='shipments_received', to='shipping.recipientaddress'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='shipment',
            name='sender',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='shipments_sent', to='shipping.senderaddress'),
            preserve_default=False,
        ),
    ]
