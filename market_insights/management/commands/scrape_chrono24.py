import os
import json
import time
import re
from datetime import datetime
import tempfile
import uuid
import shutil
from decimal import Decimal
from django.core.management.base import BaseCommand
from market_insights.models import MarketData
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


class Command(BaseCommand):
    help = 'Scrapes watch data from Chrono24 and saves to MarketData model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max_pages',
            type=int,
            default=20,
            help='Maximum number of pages to scrape'
        )

    def check_and_close_popup(self, driver):
        """
        Check for popups and close them
        
        Args:
            driver: Selenium WebDriver instance
        
        Returns:
            Boolean indicating if a popup was closed
        """
        try:
            # Look for common popup elements - adjust these selectors as needed
            popup_selectors = [
                "//button[contains(@class, 'close')]",
                "//button[contains(text(), 'Close')]",
                "//button[contains(text(), 'No thanks')]",
                "//button[contains(text(), 'Not now')]",
                "//div[contains(@class, 'modal') or contains(@class, 'popup')]//button",
                "//div[contains(@class, 'modal-close')]",
                "//div[contains(@class, 'modal') or contains(@class, 'popup')]//span[contains(@class, 'close')]",
                "//div[contains(@class, 'dialog')]//button",
                "//button[contains(@aria-label, 'Close')]",
                "//button[contains(@class, 'modal-close')]"
            ]
            
            # Try each selector
            for selector in popup_selectors:
                buttons = driver.find_elements(By.XPATH, selector)
                if buttons:
                    self.stdout.write(f"Found popup with selector: {selector}")
                    for button in buttons:
                        if button.is_displayed():
                            button.click()
                            self.stdout.write("Closed popup")
                            time.sleep(1.5)  # Wait longer for popup to close
                            return True
            
            # Try clicking on the document body to dismiss popups
            body = driver.find_elements(By.TAG_NAME, "body")
            if body:
                # Click on edges/corners to avoid clicking on main content
                driver.execute_script("arguments[0].click();", body[0])
                
            # Check for overlay/modal background and click it
            overlays = driver.find_elements(By.XPATH, "//div[contains(@class, 'overlay') or contains(@class, 'modal-backdrop')]")
            if overlays:
                for overlay in overlays:
                    if overlay.is_displayed():
                        driver.execute_script("arguments[0].click();", overlay)
                        self.stdout.write("Clicked on overlay to dismiss popup")
                        time.sleep(1.5)
                        return True
                        
            # Press ESC key to close popups
            from selenium.webdriver.common.keys import Keys
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(1)
            
            return False
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error handling popup: {str(e)}"))
            return False

    def scrape_chrono24_watches(self, max_pages=20):
        """
        Scrape watches from chrono24.com with improved infinite scroll handling
        
        Args:
            max_pages: Maximum number of pages to scrape
        
        Returns:
            List of watch dictionaries
        """
        # Setup Chrome with anti-detection measures
        options = Options()
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Create a unique user data directory with UUID and ensure it's clean
        unique_dir = None
        driver = None
        
        try:
            # Generate a truly unique directory name using UUID
            unique_id = uuid.uuid4().hex
            unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{unique_id}")
            
            # Ensure directory doesn't exist before creating it
            if os.path.exists(unique_dir):
                shutil.rmtree(unique_dir)
            
            # Create fresh directory
            os.makedirs(unique_dir, exist_ok=True)
            
            options.add_argument(f"--user-data-dir={unique_dir}")
            self.stdout.write(f"Created user data directory: {unique_dir}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error setting up user data directory: {str(e)}"))
            # Fallback to using a simpler directory name if UUID fails
            unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_fallback_{int(time.time())}")
            options.add_argument(f"--user-data-dir={unique_dir}")
        
        all_watches_data = []
        
        try:
            driver = webdriver.Chrome(options=options)
            
            # Mask WebDriver
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Handle cookie consent once at the beginning
            base_url = 'https://www.chrono24.com/watches/mens-watches--62.htm'
            driver.get(base_url)
            self.stdout.write(f"Loading initial URL: {base_url}")
            
            # Wait for page to load completely
            time.sleep(5)
            
            # Handle cookie consent if it appears
            try:
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'cookie') or contains(text(), 'Accept')]")
                if cookie_buttons:
                    cookie_buttons[0].click()
                    self.stdout.write("Clicked cookie consent button")
                    time.sleep(2)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Cookie handling error: {str(e)}"))
            
            # Loop through each page
            for page_num in range(1, max_pages + 1):
                page_url = f'https://www.chrono24.com/watches/mens-watches--62.htm?pageSize=120&resultview=list&showpage={page_num}'
                self.stdout.write(f"\n======== Scraping Page {page_num}/{max_pages} ========")
                self.stdout.write(f"Loading URL: {page_url}")
                
                driver.get(page_url)
                time.sleep(5)  # Wait for page to load
                
                # Check for popups
                self.check_and_close_popup(driver)
                
                # Scroll to load all content
                last_height = driver.execute_script("return document.body.scrollHeight")
                for _ in range(3):  # Scroll a few times to load more content
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height
                
                # Get page source after everything is loaded
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Check if we've reached the end of results
                no_results = soup.select('.no-results-container') or soup.select('.no-results')
                if no_results:
                    self.stdout.write(f"No more results found on page {page_num}. Stopping pagination.")
                    break
                
                # Find watch listing items
                watch_items = soup.select('.article-item')
                self.stdout.write(f"Found {len(watch_items)} watch items on page {page_num}")
                
                if not watch_items:
                    self.stdout.write(f"No watch items found on page {page_num}. Checking if we reached the end.")
                    # Check for pagination indicators that we're at the end
                    if soup.select('.pagination-end, .no-more-results'):
                        self.stdout.write("Reached the end of pagination. Stopping.")
                        break
                
                # Extract data using both Selenium and BeautifulSoup for better coverage
                selenium_watch_items = driver.find_elements(By.CSS_SELECTOR, '.article-item')
                
                # Ensure we have matching numbers of items
                min_items = min(len(watch_items), len(selenium_watch_items))
                
                for i in range(min_items):
                    try:
                        soup_item = watch_items[i]
                        selenium_item = selenium_watch_items[i]
                        
                        watch_data = {}
                        watch_data['page'] = page_num  # Track which page this came from
                        
                        # Extract item ID and URL
                        links = selenium_item.find_elements(By.TAG_NAME, 'a')
                        for link in links:
                            href = link.get_attribute('href') or ''
                            id_match = re.search(r'id(\d+)\.htm', href)
                            if id_match:
                                watch_data['item_id'] = f"chrono24_{id_match.group(1)}"
                                watch_data['product_url'] = href
                                break
                        
                        # Extract watch name using Selenium
                        try:
                            name_elements = selenium_item.find_elements(By.CSS_SELECTOR, '.text-bold, h2, h3, .article-title')
                            for element in name_elements:
                                name_text = element.text.strip()
                                if name_text and len(name_text) > 5:  # Simple filter for meaningful names
                                    watch_data['name'] = name_text
                                    break
                        except:
                            pass
                        
                        # Try with BeautifulSoup if Selenium didn't find a name
                        if 'name' not in watch_data:
                            name_element = soup_item.find(class_=lambda c: c and ('title' in c.lower() or 'name' in c.lower() or 'text-bold' in c))
                            if name_element:
                                watch_data['name'] = name_element.text.strip()
                        
                        # Extract price using Selenium
                        try:
                            price_elements = selenium_item.find_elements(By.CSS_SELECTOR, '.text-bold, .price, .article-price')
                            for element in price_elements:
                                price_text = element.text.strip()
                                if any(currency in price_text for currency in ['$', '€', '£', 'USD', 'EUR']):
                                    watch_data['price_text'] = price_text
                                    # Extract numeric price
                                    price_match = re.search(r'[\$€£]([0-9,]+)', price_text)
                                    if price_match:
                                        price = price_match.group(1).replace(',', '')
                                        try:
                                            watch_data['price'] = int(price)
                                        except ValueError:
                                            pass
                                    break
                        except:
                            pass
                        
                        # Try with BeautifulSoup if Selenium didn't find a price
                        if 'price' not in watch_data:
                            # Look for any element containing price indicators
                            price_text = None
                            for element in soup_item.find_all(text=True):
                                if any(currency in element for currency in ['$', '€', '£', 'USD', 'EUR']):
                                    price_text = element.strip()
                                    if price_text:
                                        price_match = re.search(r'[\$€£]([0-9,]+)', price_text)
                                        if price_match:
                                            price = price_match.group(1).replace(',', '')
                                            try:
                                                watch_data['price'] = int(price)
                                                watch_data['price_text'] = price_text
                                                break
                                            except ValueError:
                                                pass
                                                
                        # ENHANCED IMAGE EXTRACTION - similar to your bezel implementation
                        # Method 1: Use JavaScript to get computed background images
                        try:
                            # Execute JavaScript to get background images from computed style
                            script = """
                            var element = arguments[0];
                            var allElements = element.querySelectorAll('*');
                            var imagesFound = [];
                            
                            for (var i = 0; i < allElements.length; i++) {
                                var el = allElements[i];
                                var style = window.getComputedStyle(el);
                                var bg = style.backgroundImage;
                                if (bg && bg !== 'none' && bg.includes('url(')) {
                                    var url = bg.replace(/^url\\(['"](.+?)['"]\\)$/, '$1');
                                    if (!url.includes('data:image/svg') && !url.endsWith('.svg')) {
                                        imagesFound.push(url);
                                    }
                                }
                            }
                            
                            return imagesFound;
                            """
                            computed_images = driver.execute_script(script, selenium_item)
                            if computed_images:
                                watch_data['image_url'] = computed_images[0]
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"Error getting computed background images: {str(e)}"))
                        
                        # Method 2: Direct from Selenium's img tags
                        if 'image_url' not in watch_data:
                            try:
                                imgs = selenium_item.find_elements(By.TAG_NAME, 'img')
                                for img in imgs:
                                    # Check multiple attributes where images might be stored
                                    for attr in ['src', 'data-src', 'data-original', 'data-lazy-src', 'data-srcset']:
                                        src = img.get_attribute(attr)
                                        if src and not src.endswith('svg') and 'data:image/svg' not in src:
                                            # Filter out tiny images and icons
                                            if 'icon' not in src.lower() and 'logo' not in src.lower():
                                                watch_data['image_url'] = src
                                                break
                                    
                                    # If we found an image, break out of the loop
                                    if 'image_url' in watch_data:
                                        break
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f"Error with Selenium img extraction: {str(e)}"))
                        
                        # Make sure URLs are absolute
                        if 'image_url' in watch_data:
                            image_url = watch_data['image_url']
                            if image_url.startswith('//'):
                                watch_data['image_url'] = 'https:' + image_url
                            elif image_url.startswith('/'):
                                watch_data['image_url'] = 'https://www.chrono24.com' + image_url
                        
                        # Extract details from the full text
                        full_text = selenium_item.text
                        
                        # Look for reference number
                        ref_match = re.search(r'[Rr]eference\s*(?:number)?[:\s]+([A-Za-z0-9.-]+)', full_text)
                        if ref_match:
                            watch_data['reference_number'] = ref_match.group(1)
                        
                        # Look for brand - first try direct brand extraction
                        brand_element = soup_item.find(class_=lambda c: c and ('brand' in c.lower()))
                        if brand_element:
                            watch_data['brand'] = brand_element.text.strip()
                        
                        # If no brand found, try with common watch brands
                        if 'brand' not in watch_data:
                            brand_candidates = ['Rolex', 'Omega', 'Breitling', 'Tag Heuer', 'Patek Philippe', 
                                                'Audemars Piguet', 'IWC', 'Cartier', 'Jaeger-LeCoultre', 
                                                'Panerai', 'Hublot', 'Zenith', 'Tudor', 'Grand Seiko', 'Seiko']
                            
                            for brand in brand_candidates:
                                # Use regex to find standalone brand names, not inside other words
                                pattern = r'\b' + re.escape(brand) + r'\b'
                                if re.search(pattern, full_text, re.IGNORECASE):
                                    watch_data['brand'] = brand
                                    break
                                    
                            # If still no brand found, try to extract it from the name
                            if 'brand' not in watch_data and 'name' in watch_data:
                                for brand in brand_candidates:
                                    pattern = r'\b' + re.escape(brand) + r'\b'
                                    if re.search(pattern, watch_data['name'], re.IGNORECASE):
                                        watch_data['brand'] = brand
                                        break
                        
                        # Look for condition
                        condition_match = re.search(r'(?:Condition|State)[:\s]+([A-Za-z]+)', full_text)
                        if condition_match:
                            watch_data['condition'] = condition_match.group(1)
                        
                        # Only add watches with required info for MarketData model
                        if ('item_id' in watch_data and ('price' in watch_data or 'name' in watch_data)):
                            all_watches_data.append(watch_data)
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing item {i} on page {page_num}: {str(e)}"))
                
                # Check if we should continue to the next page
                next_page_indicators = driver.find_elements(By.CSS_SELECTOR, '.pagination-next, a[rel="next"]')
                if not next_page_indicators:
                    self.stdout.write(f"No 'next page' indicator found after page {page_num}. Stopping pagination.")
                    break
                    
                # Add a random delay between pages to avoid being blocked
                delay = 3 + (page_num % 3)  # Vary the delay between 3-5 seconds
                self.stdout.write(f"Waiting {delay} seconds before loading next page...")
                time.sleep(delay)
            
            # Generate statistics
            self.stdout.write(f"\nFinished scraping {len(all_watches_data)} watches across {page_num} pages")
            
            # Count items with images
            items_with_images = sum(1 for watch in all_watches_data if 'image_url' in watch)
            if all_watches_data:
                percentage = (items_with_images/len(all_watches_data))*100
                self.stdout.write(f"Items with images: {items_with_images}/{len(all_watches_data)} ({percentage:.1f}%)")
            
            # Count items with brands
            items_with_brands = sum(1 for watch in all_watches_data if 'brand' in watch)
            if all_watches_data:
                percentage = (items_with_brands/len(all_watches_data))*100
                self.stdout.write(f"Items with brands: {items_with_brands}/{len(all_watches_data)} ({percentage:.1f}%)")
            
            # Count items with reference numbers
            items_with_refs = sum(1 for watch in all_watches_data if 'reference_number' in watch)
            if all_watches_data:
                percentage = (items_with_refs/len(all_watches_data))*100
                self.stdout.write(f"Items with reference numbers: {items_with_refs}/{len(all_watches_data)} ({percentage:.1f}%)")
            
            return all_watches_data
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during scraping: {str(e)}"))
            return []
            
        finally:
            try:
                if driver:
                    driver.quit()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error closing Chrome driver: {str(e)}"))
                
            # Clean up the temporary directory
            try:
                if unique_dir and os.path.exists(unique_dir):
                    shutil.rmtree(unique_dir)
                    self.stdout.write(f"Cleaned up user data directory: {unique_dir}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error cleaning up user data directory: {str(e)}"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Chrono24 watch data extraction...'))
        
        max_pages = options['max_pages']
        
        try:
            # Scrape data from Chrono24
            watches = self.scrape_chrono24_watches(max_pages=max_pages)
            self.stdout.write(self.style.SUCCESS(f"Successfully scraped {len(watches)} watches"))
            
            # Save each watch to the MarketData model
            saved_count = 0
            skipped_count = 0
            
            for watch in watches:
                # Skip if no item_id
                item_id = watch.get('item_id')
                if not item_id:
                    skipped_count += 1
                    continue
                
                # Check if item already exists in database
                if MarketData.objects.filter(item_id=item_id).exists():
                    self.stdout.write(f"Item {item_id} already exists in database, skipping...")
                    skipped_count += 1
                    continue
                
                # Convert price to Decimal if it exists
                price_value = Decimal('0')
                if watch.get('price'):
                    try:
                        price_value = Decimal(str(watch['price']))
                    except (ValueError, TypeError):
                        self.stdout.write(self.style.WARNING(f"Could not convert price for item {item_id}"))
                
                # Create new MarketData entry
                market_data = MarketData(
                    source='chrono24',
                    price=price_value,
                    name=watch.get('name'),
                    image_url=watch.get('image_url'),
                    reference_number=watch.get('reference_number'),
                    brand=watch.get('brand'),
                )
                
                # Save to database
                try:
                    market_data.save()
                    saved_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error saving item {item_id}: {str(e)}"))
                    skipped_count += 1
            
            # Save raw data to JSON as backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chrono24_watches_{timestamp}.json"
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(watches, f, indent=2, ensure_ascii=False)
            
            self.stdout.write(self.style.SUCCESS(f'Saved {saved_count} new items to database, skipped {skipped_count} items'))
            self.stdout.write(self.style.SUCCESS(f'Raw data backup saved to {filename}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during scraping: {str(e)}"))