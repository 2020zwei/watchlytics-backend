from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import (
    Shipment, 
    SenderAddress, 
    RecipientAddress, 
    ShippingConfig,
    NotificationEmail, 
    ShipmentProduct
)
from .serializers import (
    ShipmentCreateSerializer,
    ShipmentDetailSerializer,
    SenderAddressSerializer,
    RecipientAddressSerializer,
    VerifyAddressSerializer,
    ShippingCostCalculationSerializer
)
from shipping.services.ifs_api_service import IFSAPIService


class SenderAddressViewSet(viewsets.ModelViewSet):
    """
    API endpoints for sender addresses
    """
    queryset = SenderAddress.objects.all()
    serializer_class = SenderAddressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = SenderAddress.objects.all()
        
        # Filter by is_primary if specified
        is_primary = self.request.query_params.get('is_primary', None)
        if is_primary is not None:
            is_primary = is_primary.lower() == 'true'
            queryset = queryset.filter(is_primary=is_primary)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def sync_from_ifs(self, request):
        """
        Sync sender addresses from IFS system
        """
        try:
            ifs_service = IFSAPIService()
            addresses_data = ifs_service.get_client_address_list()
            
            # Process and save addresses
            synced_addresses = []
            for address in addresses_data.get('address_list', []):
                address_detail = ifs_service.get_client_address_data(address['client_address_id'])
                address_data = address_detail.get('address_data', {})
                
                # Check if address already exists
                sender, created = SenderAddress.objects.update_or_create(
                    ifs_id=address['client_address_id'],
                    defaults={
                        'name': address_data.get('name', ''),
                        'company_name': address_data.get('company_name', ''),
                        'address1': address_data.get('address1', ''),
                        'address2': address_data.get('address2', ''),
                        'city': address_data.get('city', ''),
                        'state': address_data.get('state', ''),
                        'zip_code': address_data.get('zip', ''),
                        'country': address_data.get('country', 'United States'),
                        'phone': address_data.get('phone', ''),
                        'email': address_data.get('email', ''),
                        'is_residential': address_data.get('is_residential', False) == 'Y',
                    }
                )
                synced_addresses.append(SenderAddressSerializer(sender).data)
            
            return Response({
                'status': 'success',
                'message': f'Successfully synced {len(synced_addresses)} sender addresses',
                'addresses': synced_addresses
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecipientAddressViewSet(viewsets.ModelViewSet):
    """
    API endpoints for recipient addresses
    """
    queryset = RecipientAddress.objects.all()
    serializer_class = RecipientAddressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = RecipientAddress.objects.all()
        
        # Filter by search term if provided
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                name__icontains=search
            ) | queryset.filter(
                company_name__icontains=search
            ) | queryset.filter(
                address1__icontains=search
            ) | queryset.filter(
                city__icontains=search
            ) | queryset.filter(
                zip_code__icontains=search
            )
            
        return queryset
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify recipient address with FedEx via IFS
        """
        serializer = VerifyAddressSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            ifs_service = IFSAPIService()
            result = ifs_service.verify_recipient_address(serializer.validated_data)
            
            # If recipient_id was provided, update the address verification status
            recipient_id = serializer.validated_data.get('recipient_id')
            if recipient_id:
                recipient = get_object_or_404(RecipientAddress, pk=recipient_id)
                recipient.is_verified = True
                recipient.save()
            
            return Response({
                'status': 'success',
                'data': result
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def sync_from_ifs(self, request):
        """
        Sync recipient addresses from IFS system
        """
        try:
            ifs_service = IFSAPIService()
            search_term = request.query_params.get('search', '')
            
            if search_term:
                addresses_data = ifs_service.search_recipients(search_term)
            else:
                addresses_data = ifs_service.get_recipient_list()
            
            # Process and save addresses
            synced_addresses = []
            for address in addresses_data.get('recipient_list', []):
                address_detail = ifs_service.get_recipient_data(address['recipient_id'])
                address_data = address_detail.get('recipient_data', {})
                
                # Check if address already exists
                recipient, created = RecipientAddress.objects.update_or_create(
                    ifs_id=address['recipient_id'],
                    defaults={
                        'name': address_data.get('name', ''),
                        'company_name': address_data.get('company_name', ''),
                        'label_name': address_data.get('label_name', ''),
                        'address1': address_data.get('address1', ''),
                        'address2': address_data.get('address2', ''),
                        'city': address_data.get('city', ''),
                        'state': address_data.get('state', ''),
                        'zip_code': address_data.get('zip', ''),
                        'country': address_data.get('country', 'United States'),
                        'phone': address_data.get('phone', ''),
                        'email': address_data.get('email', ''),
                        'is_residential': address_data.get('is_residential', False) == 'Y',
                        'is_verified': address_data.get('is_verified', False) == 'Y'
                    }
                )
                synced_addresses.append(RecipientAddressSerializer(recipient).data)
            
            return Response({
                'status': 'success',
                'message': f'Successfully synced {len(synced_addresses)} recipient addresses',
                'addresses': synced_addresses
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_by_zipcode(self, request):
        """
        Get city and state based on provided zip code
        """
        zip_code = request.query_params.get('zip_code')
        if not zip_code:
            return Response({
                'status': 'error',
                'message': 'zip_code parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            ifs_service = IFSAPIService()
            result = ifs_service.get_zipcode_details(zip_code)
            
            return Response({
                'status': 'success',
                'data': result
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShipmentViewSet(viewsets.ModelViewSet):
    """
    API endpoints for shipments - with combined recipient, sender and package information
    """
    queryset = Shipment.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ShipmentCreateSerializer
        return ShipmentDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Create shipment with combined recipient, sender, and package information
        """
        # Extract sender and recipient data if provided inline
        sender_data = request.data.pop('sender_data', None)
        recipient_data = request.data.pop('recipient_data', None)
        
        # Create or update sender if sender_data provided
        if sender_data:
            sender_id = sender_data.pop('id', None)
            if sender_id:
                # Update existing sender
                sender = get_object_or_404(SenderAddress, pk=sender_id)
                for key, value in sender_data.items():
                    setattr(sender, key, value)
                sender.save()
            else:
                # Create new sender
                sender_serializer = SenderAddressSerializer(data=sender_data)
                if sender_serializer.is_valid():
                    sender = sender_serializer.save()
                else:
                    return Response(sender_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Set sender ID in the request data
            request.data['sender'] = sender.id
        
        # Create or update recipient if recipient_data provided
        if recipient_data:
            recipient_id = recipient_data.pop('id', None)
            if recipient_id:
                # Update existing recipient
                recipient = get_object_or_404(RecipientAddress, pk=recipient_id)
                for key, value in recipient_data.items():
                    setattr(recipient, key, value)
                recipient.save()
            else:
                # Create new recipient
                recipient_serializer = RecipientAddressSerializer(data=recipient_data)
                if recipient_serializer.is_valid():
                    recipient = recipient_serializer.save()
                else:
                    return Response(recipient_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Set recipient ID in the request data
            request.data['recipient'] = recipient.id
        
        # Set default shipping_cost to avoid not-null constraint violation
        if 'shipping_cost' not in request.data:
            request.data['shipping_cost'] = 0.00
        
        # Now proceed with the standard shipment creation
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Create shipment object first
        shipment = serializer.save()
        
        try:
            # Connect to IFS API to create shipping label
            ifs_service = IFSAPIService()
            
            # Prepare shipment data for IFS
            sender = shipment.sender
            recipient = shipment.recipient
            
            shipment_data = {
                'client_address_id': sender.ifs_id,
                'recipient_id': recipient.ifs_id if recipient.ifs_id else None,
                
                # Include all recipient data in case recipient_id is not in IFS
                'client_name': recipient.name,
                'client_company_name': recipient.company_name or '',
                'client_label_name': recipient.label_name or '',
                'client_address1': recipient.address1,
                'client_address2': recipient.address2 or '',
                'client_city': recipient.city,
                'client_state': recipient.state,
                'client_zip': recipient.zip_code,
                'client_country': recipient.country,
                'client_phone': recipient.phone or '',
                'client_email': recipient.email or '',
                'is_residential': 'Y' if recipient.is_residential else 'N',
                
                # Shipment information
                'packaging_type': shipment.package_type,
                'service_type': shipment.service_type,
                'weight': float(shipment.package_weight),
                'length': float(shipment.package_length) if shipment.package_length else None,
                'width': float(shipment.package_width) if shipment.package_width else None,
                'height': float(shipment.package_height) if shipment.package_height else None,
                'declared_value': float(shipment.declared_value),
                'payment_type': shipment.payment_type,
                'account_number': shipment.account_number,
                'reference': shipment.reference or '',
                'reference_on_label': 'Y' if shipment.reference_on_label else 'N',
                'signature_type': shipment.signature_type,
                'saturday_delivery': 'Y' if shipment.saturday_delivery else 'N',
                'pickup_date': shipment.pickup_date.strftime('%Y-%m-%d'),
                'label_format': shipment.label_format,
                
                # Hold at location
                'hold_at_location': 'Y' if shipment.hold_at_location else 'N',
            }
            
            # Add hold at location details if applicable
            if shipment.hold_at_location:
                shipment_data.update({
                    'hal_contact_person': shipment.hal_contact_person,
                    'hal_company_name': shipment.hal_company_name,
                    'hal_address': shipment.hal_address,
                    'hal_city': shipment.hal_city,
                    'hal_state': shipment.hal_state,
                    'hal_zip': shipment.hal_zip_code,
                    'hal_phone': shipment.hal_phone,
                    'hal_location_property': shipment.hal_location_property or '',
                })
            
            # Add notification emails
            notification_emails = shipment.notification_emails.all()
            for i, email in enumerate(notification_emails):
                shipment_data[f'client_email{i+1}'] = email.email
                shipment_data[f'client_email{i+1}_name'] = email.name
                shipment_data[f'client_email{i+1}_message'] = email.message or ''
            
            # Add international shipment details if applicable
            if shipment.is_international:
                shipment_data.update({
                    'is_international': 'Y',
                    'duties_taxes_paid_by': shipment.duties_taxes_paid_by,
                    'customs_value': float(shipment.customs_value or 0),
                })
                
                # Add products for international shipments
                products = shipment.products.all()
                for i, product in enumerate(products):
                    shipment_data[f'product{i+1}_name'] = product.name
                    shipment_data[f'product{i+1}_description'] = product.description
                    shipment_data[f'product{i+1}_hts_number'] = product.hts_number or ''
                    shipment_data[f'product{i+1}_quantity'] = product.quantity
                    shipment_data[f'product{i+1}_weight_unit'] = product.weight_unit
                    shipment_data[f'product{i+1}_gross_weight'] = float(product.gross_weight)
                    shipment_data[f'product{i+1}_value'] = float(product.value)
                    shipment_data[f'product{i+1}_origin_country'] = product.origin_country
            
            # Create label via IFS API
            result = ifs_service.create_shipping_label(shipment_data)
            
            # Update shipment with data from API response
            label_data = result.get('label_data', {})
            shipment.ifs_shipment_id = label_data.get('shipment_id')
            shipment.tracking_number = label_data.get('tracking_no')
            shipment.zone_id = label_data.get('zone_id')
            shipment.shipping_cost = label_data.get('shipping_cost', shipment.shipping_cost)  # Use existing value as fallback
            shipment.status = 'label_created'
            
            # Get document URLs
            docs = ifs_service.get_shipment_documents(shipment_id=shipment.ifs_shipment_id)
            docs_data = docs.get('options_data', {})
            
            shipment.label_url = docs_data.get('shipping_label_url')
            shipment.commercial_invoice_url = docs_data.get('commercial_invoice_url')
            shipment.return_label_url = docs_data.get('return_label_url')
            shipment.receipt_url = docs_data.get('receipt_url')
            
            # Save updated shipment
            shipment.save()
            
            # Return detailed shipment data
            serializer = ShipmentDetailSerializer(shipment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # If API call fails, delete the shipment and return error
            shipment.delete()
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShippingCalculationView(generics.GenericAPIView):
    """
    Calculate shipping costs
    """
    serializer_class = ShippingCostCalculationSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get address information
            sender = get_object_or_404(SenderAddress, pk=serializer.validated_data['sender_id'])
            recipient = get_object_or_404(RecipientAddress, pk=serializer.validated_data['recipient_id'])
            
            # Prepare data for IFS API
            calc_data = {
                'client_address_id': sender.ifs_id,
                'client_country': recipient.country,
                'client_state': recipient.state,
                'client_zip': recipient.zip_code,
                'packaging_type': serializer.validated_data['package_type'],
                'service_type': serializer.validated_data['service_type'],
                'weight': float(serializer.validated_data['package_weight']),
                'declared_value': float(serializer.validated_data['declared_value']),
                'pickup_date': serializer.validated_data['pickup_date'].strftime('%Y-%m-%d'),
                'payment_type': serializer.validated_data['payment_type'],
                'account_number': serializer.validated_data.get('account_number', ''),
                'signature_type': serializer.validated_data['signature_type'],
                'is_residential': 'Y' if serializer.validated_data['residential'] else 'N',
                'saturday_delivery': 'Y' if serializer.validated_data['saturday_delivery'] else 'N',
                'hold_at_location': 'Y' if serializer.validated_data['hold_at_location'] else 'N',
            }
            
            # Add package dimensions if provided
            if serializer.validated_data.get('package_length'):
                calc_data['length'] = float(serializer.validated_data['package_length'])
            if serializer.validated_data.get('package_width'):
                calc_data['width'] = float(serializer.validated_data['package_width'])
            if serializer.validated_data.get('package_height'):
                calc_data['height'] = float(serializer.validated_data['package_height'])
            
            # Add HAL data if applicable
            if serializer.validated_data['hold_at_location'] and serializer.validated_data.get('hal_data'):
                hal_data = serializer.validated_data['hal_data']
                calc_data.update({
                    'hal_contact_person': hal_data.get('contact_person', ''),
                    'hal_company_name': hal_data.get('company_name', ''),
                    'hal_address': hal_data.get('address', ''),
                    'hal_city': hal_data.get('city', ''),
                    'hal_state': hal_data.get('state', ''),
                    'hal_zip': hal_data.get('zip_code', ''),
                    'hal_phone': hal_data.get('phone', ''),
                })
            
            # Add international shipping data if applicable
            if serializer.validated_data['is_international']:
                calc_data['is_international'] = 'Y'
                calc_data['duties_taxes_paid_by'] = serializer.validated_data.get('duties_taxes_paid_by', '')
                
                # Add products for international shipments
                products = serializer.validated_data.get('products', [])
                for i, product in enumerate(products):
                    calc_data[f'product{i+1}_name'] = product.get('name', '')
                    calc_data[f'product{i+1}_description'] = product.get('description', '')
                    calc_data[f'product{i+1}_hts_number'] = product.get('hts_number', '')
                    calc_data[f'product{i+1}_quantity'] = product.get('quantity', 1)
                    calc_data[f'product{i+1}_weight_unit'] = product.get('weight_unit', 'LB')
                    calc_data[f'product{i+1}_gross_weight'] = float(product.get('gross_weight', 0))
                    calc_data[f'product{i+1}_value'] = float(product.get('value', 0))
                    calc_data[f'product{i+1}_origin_country'] = product.get('origin_country', 'United States')
            
            # Calculate shipping cost
            ifs_service = IFSAPIService()
            result = ifs_service.calculate_shipping_cost(calc_data)
            
            # Extract cost data
            cost_data = result.get('cost_data', {})
            
            return Response({
                'status': 'success',
                'base_charge': cost_data.get('base_charge', 0),
                'fuel_surcharge': cost_data.get('fuel_surcharge', 0),
                'residential_fee': cost_data.get('residential_fee', 0),
                'declared_value_fee': cost_data.get('declared_value_fee', 0),
                'additional_fees': cost_data.get('additional_fees', {}),
                'total_cost': cost_data.get('total_cost', 0),
                'zone_id': cost_data.get('zone_id'),
                'estimated_delivery': cost_data.get('estimated_delivery'),
                'currency': cost_data.get('currency', 'USD')
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ShippingConfigView(generics.RetrieveUpdateAPIView):
    """
    Get and update IFS API configuration
    """
    queryset = ShippingConfig.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return ShippingConfig.objects.filter(is_active=True).first()
    
    def get(self, request, *args, **kwargs):
        config = self.get_object()
        if not config:
            return Response({
                'status': 'error',
                'message': 'No active shipping configuration found'
            }, status=status.HTTP_404_NOT_FOUND)
            
        return Response({
            'status': 'success',
            'id': config.id,
            'auth_key': '********',  # Mask actual key for security
            'is_active': config.is_active,
            'created_at': config.created_at,
            'updated_at': config.updated_at,
        })
    
    def put(self, request, *args, **kwargs):
        config = self.get_object()
        if not config:
            # Create new config if none exists
            config = ShippingConfig.objects.create(
                auth_key=request.data.get('auth_key'),
                is_active=True
            )
            return Response({
                'status': 'success',
                'message': 'Shipping configuration created',
                'id': config.id,
                'is_active': config.is_active,
                'created_at': config.created_at,
                'updated_at': config.updated_at,
            }, status=status.HTTP_201_CREATED)
        
        # Update existing config
        config.auth_key = request.data.get('auth_key', config.auth_key)
        config.save()
        
        return Response({
            'status': 'success',
            'message': 'Shipping configuration updated',
            'id': config.id,
            'is_active': config.is_active,
            'created_at': config.created_at,
            'updated_at': config.updated_at,
        })
    
    @action(detail=False, methods=['get'])
    def test_connection(self, request):
        """
        Test connection to IFS API
        """
        try:
            ifs_service = IFSAPIService()
            result = ifs_service.get_basic_data()
            
            return Response({
                'status': 'success',
                'message': 'Connection to IFS API successful',
                'data': result
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Connection to IFS API failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)