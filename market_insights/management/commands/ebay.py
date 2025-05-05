import os
import sys
from django.core.management.base import BaseCommand
import base64
import requests
import json
import re
from django.conf import settings
from datetime import datetime
from decimal import Decimal

# Import the MarketData model
from market_insights.models import MarketData

class Command(BaseCommand):
    help = 'Fetches watch data from eBay API and saves to MarketData model'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting eBay watch data extraction...'))
        
        # Get credentials from Django settings
        client_id = settings.EBAY_CLIENT_ID
        client_secret = settings.EBAY_CLIENT_SECRET
        
        # Base64 encode client_id:client_secret
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        
        # eBay OAuth token URL
        token_url = "https://api.ebay.com/identity/v1/oauth2/token"
        
        # Request headers and body
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        # Get access token
        self.stdout.write('Getting eBay access token...')
        token_response = requests.post(token_url, headers=headers, data=data)
        token_json = token_response.json()
        
        access_token = token_json.get("access_token")
        
        if not access_token:
            self.stdout.write(self.style.ERROR('Failed to get access token'))
            return
        
        self.stdout.write(self.style.SUCCESS('Access token acquired successfully'))
        
        # ---------- Search items ----------
        
        # Brands to search for
        brands = [
            "Rolex", "Audemars Piguet", "Patek Philippe", "Richard Mille",
            "Panerai", "Breitling", "Omega", "Glashutte", "Franck Muller",
            "Cartier", "Hublot"
        ]
        
        query = ", ".join(brands)
        category_id = "31387"  # Set appropriate eBay category ID
        
        search_url = f"https://api.ebay.com/buy/browse/v1/item_summary/search?q=({query})&category_ids={category_id}&limit=50"
        
        search_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        self.stdout.write('Searching for watch items...')
        search_response = requests.get(search_url, headers=search_headers)
        search_json = search_response.json()
        
        # Function to extract reference number from title
        def extract_reference_number(title, brand):
            """
            Extract potential reference numbers from watch titles based on different patterns
            """
            # Convert title to uppercase for easier matching
            title_upper = title.upper()
            
            # Different patterns for reference numbers based on brand and common formats
            
            # Pattern 1: Numbers following brand name with optional letters (e.g., "ROLEX 124300")
            p1 = re.search(r'(?:' + re.escape(brand.upper()) + r')\s+([A-Z0-9\-\.]+)', title_upper)
            
            # Pattern 2: Numbers with optional letters at the end of the title (e.g., "Watch 116519")
            p2 = re.search(r'[^A-Z]([A-Z0-9\-\.]{5,12})(?:\s+#[A-Z0-9]+)?$', title_upper)
            
            # Pattern 3: Numbers with dots or dashes (e.g., "210.32.42.20.03.001")
            p3 = re.search(r'([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', title_upper)
            
            # Pattern 4: Numbers after "REF" or similar indicators
            p4 = re.search(r'(?:REF|REFERENCE|REF\.)?\s+([A-Z0-9\-\.]+)', title_upper)
            
            # Pattern 5: Numbers preceded by hash or number sign (#Mo214)
            p5 = re.search(r'#([A-Z0-9]+)', title_upper)
            
            # Check patterns in order of specificity
            if p3:
                return p3.group(1)
            elif p1:
                return p1.group(1)
            elif p2:
                return p2.group(1)
            elif p5:
                return p5.group(1)
            elif p4:
                return p4.group(1)
            
            # If no pattern matches, return None
            return None
        
        # Process and save items to the MarketData model
        saved_count = 0
        skipped_count = 0
        
        if "itemSummaries" in search_json:
            for item in search_json["itemSummaries"]:
                title = item.get("title", "")
                item_id = item.get("itemId", "")
                
                # Skip if no item_id (unlikely but safeguard)
                if not item_id:
                    skipped_count += 1
                    continue
                
                # Check if this item already exists in our database
                if MarketData.objects.filter(item_id=item_id).exists():
                    self.stdout.write(f"Item {item_id} already exists in database, skipping...")
                    skipped_count += 1
                    continue
                
                # Try to identify which brand is in the title
                identified_brand = None
                for brand in brands:
                    if brand.upper() in title.upper():
                        identified_brand = brand
                        break
                
                # If no brand identified, use a generic approach
                if not identified_brand:
                    identified_brand = "Unknown"
                
                # Extract reference number
                reference_number = extract_reference_number(title, identified_brand)
                
                # Get price data, defaulting to 0 if missing
                price_value = 0
                try:
                    if "price" in item and "value" in item["price"]:
                        price_value = Decimal(str(item["price"]["value"]))
                except (ValueError, TypeError):
                    self.stdout.write(self.style.WARNING(f"Could not convert price for item {item_id}"))
                
                # Get image URL
                image_url = ""
                if "image" in item and "imageUrl" in item["image"]:
                    image_url = item["image"]["imageUrl"]
                
                # Get listing URL if available
                listing_url = item.get("itemWebUrl", "")
                
                # Get condition
                condition = ""
                if "condition" in item:
                    condition = item["condition"]
                    condition = "new" if "new" in condition.lower() else "used"
                
                # Create new MarketData entry
                market_data = MarketData(
                    source='ebay',
                    price=price_value,
                    name=title,
                    image_url=image_url,
                    reference_number=reference_number,
                    brand=identified_brand,
                    condition=condition
                )
                
                # Save to database
                try:
                    market_data.save()
                    saved_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error saving item {item_id}: {str(e)}"))
                    skipped_count += 1
        
        # Still save a backup JSON file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"extracted_watch_data_{timestamp}.json"
        file_path = os.path.join(settings.BASE_DIR, 'data', filename)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "w") as f:
            json.dump(search_json.get("itemSummaries", []), f, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'Saved {saved_count} new items to database, skipped {skipped_count} items'))
        self.stdout.write(self.style.SUCCESS(f'Raw data backup saved to {filename}'))