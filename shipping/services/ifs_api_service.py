import requests
import json
import logging
from django.conf import settings
from datetime import datetime

from shipping.models import ShippingConfig

logger = logging.getLogger(__name__)

class IFSAPIService:
    """Service for interacting with IFS API"""
    
    def __init__(self, user=None):
        self.base_url = "https://www.ifsclients.com/client-app-api/"
        self.user = user
        self._config = None
    
    @property
    def config(self):
        """Get shipping config for current user"""
        if self._config is None:
            if self.user:
                # Multi-tenant approach
                try:
                    self._config = ShippingConfig.objects.get(user=self.user, is_active=True)
                except ShippingConfig.DoesNotExist:
                    raise Exception("No active shipping configuration found for user")
            else:
                # Single tenant approach
                self._config = ShippingConfig.objects.filter(is_active=True).first()
                if not self._config:
                    raise Exception("No active shipping configuration found")
        return self._config
    
    def get_auth_data(self):
        """Get authentication data for API requests"""
        if hasattr(self.config, 'get_auth_data'):
            # Multi-tenant
            return self.config.get_auth_data()
        else:
            # Single tenant
            return {
                'AppUserName': self.config.app_username,
                'AppPassword': self.config.app_password,
                'account_id': self.config.account_id
            }
    
    def make_request(self, endpoint, data=None):
        """Make authenticated request to IFS API"""
        url = f"{self.base_url}{endpoint}"
        
        # Get authentication data
        auth_data = self.get_auth_data()
        
        # Merge auth data with request data
        if data is None:
            data = {}
        data.update(auth_data)
        
        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"IFS API request failed: {str(e)}")
        except ValueError as e:
            raise Exception(f"Invalid JSON response from IFS API: {str(e)}")
    
    def get_basic_data(self):
        """Get basic shipping data from IFS"""
        return self.make_request("ca_basic_data.php")
    
    def get_client_address_list(self):
        """Get list of client addresses"""
        return self.make_request("ca_client_address_list.php")
    
    def get_client_address_data(self, client_address_id):
        """Get specific client address data"""
        return self.make_request("ca_client_address_data.php", {
            'client_address_id': client_address_id
        })
    
    def calculate_shipping_cost(self, shipment_data):
        """Calculate shipping cost"""
        return self.make_request("ca_calculate_cost.php", shipment_data)
    
    def create_shipping_label(self, shipment_data):
        """Create shipping label"""
        return self.make_request("ca_create_label.php", shipment_data)
    
    def verify_recipient_address(self, address_data):
        """Verify recipient address"""
        return self.make_request("ca_verify_recipient_address.php", address_data)
    
    def get_shipment_documents(self, tracking_no=None, shipment_id=None):
        """Get shipment documents"""
        data = {}
        if tracking_no:
            data['tracking_no'] = tracking_no
        if shipment_id:
            data['shipment_id'] = shipment_id
        return self.make_request("ca_shipment_view_options.php", data)
    
    def get_shipment_details(self, tracking_no=None, shipment_id=None):
        """Get detailed shipment information"""
        data = {}
        if tracking_no:
            data['tracking_no'] = tracking_no
        if shipment_id:
            data['shipment_id'] = shipment_id
            
        return self._make_request("ca_view_shipment_details.php", data)
    
    def void_shipment(self, shipment_id):
        """Void a shipment"""
        data = {
            'shipment_id': shipment_id
        }
        return self._make_request("ca_void_shipment.php", data)
    
    # Additional methods for international shipping
    
    def get_loading_port_data(self, sender_state, recipient_country):
        """Get loading port and AES information"""
        data = {
            'ca_state': sender_state,
            'client_country': recipient_country
        }
        return self._make_request("ca_get_loading_port_data.php", data)
    
    def get_products_description(self, product_name):
        """Get product descriptions for customs"""
        data = {
            'product_name': product_name
        }
        return self._make_request("ca_get_products_description.php", data)
    
    def get_products_hts_number(self, product_name, product_description):
        """Get HTS number for product"""
        data = {
            'product_name': product_name,
            'product_description': product_description
        }
        return self._make_request("ca_get_products_htsno_unit.php", data)