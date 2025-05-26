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
        parser.add_argument(
            '--debug_limit',
            type=int,
            default=None,
            help='Limit items per page for debugging (remove for production)'
        )

    def check_and_close_popup(self, driver):
        """Check for popups and close them"""
        try:
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
            
            for selector in popup_selectors:
                buttons = driver.find_elements(By.XPATH, selector)
                if buttons:
                    self.stdout.write(f"Found popup with selector: {selector}")
                    for button in buttons:
                        if button.is_displayed():
                            button.click()
                            self.stdout.write("Closed popup")
                            time.sleep(1.5)
                            return True
            
            # Try ESC key
            from selenium.webdriver.common.keys import Keys
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(1)
            
            return False
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error handling popup: {str(e)}"))
            return False

    def extract_reference_number(self, text):
        """Extract reference number from text using common patterns"""
        reference_patterns = [
            # Common reference number patterns
            r'(?:Ref\.?\s*|Reference\s*[:#]?\s*)([A-Z0-9\-\.]{4,15})',
            r'(?:Model\s*[:#]?\s*)([A-Z0-9\-\.]{4,15})',
            r'\b([A-Z]{1,3}[\-\.]?\d{3,8}[\-\.]?[A-Z0-9]*)\b',  # Pattern like GMT-Master II 126710BLNR
            r'\b(\d{4,6}[\-\.]?[A-Z]{1,4}[\-\.]?\d*)\b',  # Pattern like 116610LN
            r'\b([A-Z]\d{4,6}[A-Z]*)\b',  # Pattern like A13356
            # Rolex specific patterns
            r'\b(1\d{5}[A-Z]{0,3})\b',  # 6-digit Rolex refs starting with 1
            r'\b(m\d{5}[\-\.]?\d*)\b',  # Rolex modern refs starting with m
        ]
        
        for pattern in reference_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                ref = match.strip().upper()
                # Filter out common false positives
                if (len(ref) >= 4 and 
                    not ref.isdigit() and  # Pure numbers are usually not refs
                    not ref in ['SIZE', 'CASE', 'DIAL', 'BAND', 'YEAR'] and
                    not re.match(r'^\d{4}$', ref)):  # 4-digit years
                    return ref
        
        return None

    def scrape_chrono24_page(self, driver, page_num, debug_limit=None):
        """Scrape a single page of watches"""
        page_watches = []
        
        try:
            # Construct URL for specific page
            base_url = f'https://www.chrono24.com/watches/mens-watches--62.htm?pageSize=120&resultview=list&showpage={page_num}'
            self.stdout.write(f"Loading page {page_num}: {base_url}")
            
            driver.get(base_url)
            time.sleep(5)
            
            # Handle popups on each page
            self.check_and_close_popup(driver)
            
            # Scroll to load all content
            self.stdout.write(f"Scrolling to load all content on page {page_num}...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 5
            
            while scroll_attempts < max_scroll_attempts:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                    
                last_height = new_height
                self.stdout.write(f"Page {page_num} - Scroll attempt {scroll_attempts}: Height = {new_height}")
                
                if scroll_attempts >= 2:  # Stop if height hasn't changed for 2 attempts
                    break
            
            # Get page source and parse
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Find watch items
            selectors_to_try = [
                '.article-item',
                '.js-article-item', 
                '.list-item',
                '.rcard',
                '[data-article-id]'
            ]
            
            watch_items = []
            for selector in selectors_to_try:
                items = soup.select(selector)
                if items:
                    watch_items = items
                    self.stdout.write(f"Page {page_num}: Found {len(items)} items with selector '{selector}'")
                    break
            
            if not watch_items:
                self.stdout.write(self.style.WARNING(f"No watch items found on page {page_num}"))
                return page_watches
            
            # Apply debug limit if specified
            items_to_process = watch_items
            if debug_limit:
                items_to_process = watch_items[:debug_limit]
                self.stdout.write(f"Debug mode: Processing only {len(items_to_process)} items out of {len(watch_items)}")
            
            self.stdout.write(f"Processing {len(items_to_process)} watch items from page {page_num}...")
            
            # Process each item
            for i, soup_item in enumerate(items_to_process):
                try:
                    watch_data = {}
                    watch_data['debug_index'] = i
                    watch_data['page_number'] = page_num
                    
                    # Extract item ID
                    item_id = None
                    if soup_item.get('data-article-id'):
                        item_id = f"chrono24_{soup_item.get('data-article-id')}"
                        watch_data['item_id'] = item_id
                    
                    if not item_id:
                        links = soup_item.find_all('a', href=True)
                        for link in links:
                            href = link.get('href', '')
                            id_match = re.search(r'id(\d+)\.htm', href)
                            if id_match:
                                item_id = f"chrono24_{id_match.group(1)}"
                                watch_data['item_id'] = item_id
                                watch_data['product_url'] = href if href.startswith('http') else f"https://www.chrono24.com{href}"
                                break
                    
                    if not item_id:
                        continue
                    
                    all_text = soup_item.get_text()
                    # Extract name
                    name_selectors = ['.text-bold', 'h2', 'h3', '.article-title', '.title', '.name']
                    name = None
                    
                    for selector in name_selectors:
                        elements = soup_item.select(selector)
                        for element in elements:
                            text = element.get_text(strip=True)
                            if text and len(text) > 3 and not text.isdigit():
                                if not re.search(r'[\$€£]\d+|^\d+$|^[A-Z]{2,3}$', text):
                                    name = text
                                    watch_data['name'] = name
                                    break
                        if name:
                            break
                    
                    # Extract price
                    all_text = soup_item.get_text()
                    price_matches = re.findall(r'[\$€£]([0-9,]+)', all_text)
                    
                    if price_matches:
                        for match in price_matches:
                            try:
                                price_num = int(match.replace(',', ''))
                                if price_num > 100:
                                    watch_data['price'] = price_num
                                    watch_data['price_text'] = f"${match}"
                                    break
                            except ValueError:
                                continue
                    
                    # Extract brand
                    brand_candidates = ['Rolex', 'Omega', 'Breitling', 'Tag Heuer', 'Patek Philippe', 
                                      'Audemars Piguet', 'IWC', 'Cartier', 'Jaeger-LeCoultre', 
                                      'Panerai', 'Hublot', 'Zenith', 'Tudor', 'Grand Seiko', 'Seiko',
                                      'Montblanc', 'Chopard', 'Vacheron Constantin', 'A. Lange & Söhne']
                    
                    for brand_name in brand_candidates:
                        if re.search(r'\b' + re.escape(brand_name) + r'\b', all_text, re.IGNORECASE):
                            watch_data['brand'] = brand_name
                            break
                    
                    reference_number = None
                
                    ref_label = soup_item.find('div', class_='col-xs-12', string=lambda t: 'Reference number' in str(t))
                    if ref_label:
                        ref_value = ref_label.find_next('div', class_='col-xs-12').find('strong')
                        if ref_value:
                            reference_number = ref_value.get_text(strip=True)
                    
                    if not reference_number:
                        ref_text_div = soup_item.find('div', class_='text-sm text-sm-lg text-ellipsis')
                        if ref_text_div:
                            reference_number = ref_text_div.get_text(strip=True)
                    
                    if not reference_number:
                        all_text = soup_item.get_text()
                        reference_number = self.extract_reference_number(all_text)
                    
                    if reference_number:
                        watch_data['reference_number'] = reference_number
                    
                    # Extract image
                    img_tags = soup_item.find_all('img')
                    for img in img_tags:
                        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                            src = img.get(attr)
                            if src and not src.endswith('.svg') and 'data:image/svg' not in src:
                                if src.startswith('//'):
                                    src = 'https:' + src
                                elif src.startswith('/'):
                                    src = 'https://www.chrono24.com' + src
                                watch_data['image_url'] = src
                                break
                        if 'image_url' in watch_data:
                            break
                    
                    # Only add if we have minimum required data
                    if 'item_id' in watch_data and ('name' in watch_data or 'price' in watch_data):
                        page_watches.append(watch_data)
                        if i % 20 == 0:  # Progress update every 20 items
                            self.stdout.write(f"Page {page_num}: Processed {i+1}/{len(items_to_process)} items")
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing item {i} on page {page_num}: {str(e)}"))
            
            self.stdout.write(f"Page {page_num}: Successfully extracted {len(page_watches)} watches")
            return page_watches
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error scraping page {page_num}: {str(e)}"))
            return page_watches

    def scrape_chrono24_watches(self, max_pages=20, debug_limit=None):
        """Scrape watches from multiple pages of chrono24.com"""
        
        options = Options()
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        unique_dir = None
        driver = None
        all_watches_data = []
        
        try:
            unique_id = uuid.uuid4().hex
            unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{unique_id}")
            
            if os.path.exists(unique_dir):
                shutil.rmtree(unique_dir)
            
            os.makedirs(unique_dir, exist_ok=True)
            options.add_argument(f"--user-data-dir={unique_dir}")
            
            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Handle initial cookie consent on first page
            self.stdout.write("Loading first page to handle cookie consent...")
            driver.get('https://www.chrono24.com/watches/mens-watches--62.htm?pageSize=120&resultview=list&showpage=1')
            time.sleep(3)
            
            try:
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'cookie') or contains(text(), 'Accept') or contains(text(), 'Allow')]")
                if cookie_buttons:
                    cookie_buttons[0].click()
                    self.stdout.write("Clicked cookie consent button")
                    time.sleep(2)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Cookie handling error: {str(e)}"))
            
            # Scrape each page
            for page_num in range(1, max_pages + 1):
                self.stdout.write(f"\n{'='*50}")
                self.stdout.write(f"SCRAPING PAGE {page_num} of {max_pages}")
                self.stdout.write(f"{'='*50}")
                
                page_watches = self.scrape_chrono24_page(driver, page_num, debug_limit)
                
                if not page_watches:
                    self.stdout.write(f"No watches found on page {page_num}. Stopping.")
                    break
                
                all_watches_data.extend(page_watches)
                self.stdout.write(f"Total watches collected so far: {len(all_watches_data)}")
                
                # Add delay between pages to be respectful
                if page_num < max_pages:
                    self.stdout.write("Waiting 3 seconds before next page...")
                    time.sleep(3)
            
            self.stdout.write(f"\nSCRAPING COMPLETE: Total watches extracted: {len(all_watches_data)}")
            return all_watches_data
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during scraping: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())
            return all_watches_data
            
        finally:
            try:
                if driver:
                    driver.quit()
            except:
                pass
                
            try:
                if unique_dir and os.path.exists(unique_dir):
                    shutil.rmtree(unique_dir)
            except:
                pass

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Chrono24 watch data extraction...'))
        
        max_pages = options['max_pages']
        debug_limit = options['debug_limit']
        
        if debug_limit:
            self.stdout.write(self.style.WARNING(f"DEBUG MODE: Will only process {debug_limit} items per page"))
        
        try:
            watches = self.scrape_chrono24_watches(max_pages=max_pages, debug_limit=debug_limit)
            self.stdout.write(self.style.SUCCESS(f"Successfully scraped {len(watches)} watches from {max_pages} pages"))
            
            if not watches:
                self.stdout.write(self.style.ERROR("No watches were scraped. Check the debug output above."))
                return
            
            # Debug: Print first few watches
            self.stdout.write("\n=== SAMPLE EXTRACTED WATCHES ===")
            for i, watch in enumerate(watches[:5]):
                ref_num = watch.get('reference_number', 'No ref')
                self.stdout.write(f"Watch {i+1}: {watch.get('name', 'No name')} - ${watch.get('price', 'No price')} - Ref: {ref_num} (Page {watch.get('page_number', '?')})")
            
            # Save to database
            saved_count = 0
            skipped_count = 0
            
            self.stdout.write(f"\nSaving {len(watches)} watches to database...")
            
            for watch in watches:
                item_id = watch.get('item_id')
                if not item_id:
                    skipped_count += 1
                    continue
                
                # Check if exists
                if MarketData.objects.filter(item_id=item_id).exists():
                    skipped_count += 1
                    continue
                
                # Convert price
                price_value = Decimal('0')
                if watch.get('price'):
                    try:
                        price_value = Decimal(str(watch['price']))
                    except (ValueError, TypeError) as e:
                        self.stdout.write(self.style.WARNING(f"Could not convert price for {item_id}: {e}"))
                
                # Create MarketData entry
                try:
                    market_data = MarketData(
                        item_id=item_id,
                        source='chrono24',
                        price=price_value,
                        name=watch.get('name', ''),
                        image_url=watch.get('image_url', ''),
                        reference_number=watch.get('reference_number', ''),
                        brand=watch.get('brand', ''),
                    )
                    
                    market_data.save()
                    saved_count += 1
                    
                    if saved_count % 50 == 0:  # Progress update every 50 saves
                        self.stdout.write(f"Saved {saved_count} items so far...")
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error saving {item_id}: {str(e)}"))
                    skipped_count += 1
            
            # Save backup JSON
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"chrono24_watches_{timestamp}.json"
                
                # Create data directory if it doesn't exist
                data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
                os.makedirs(data_dir, exist_ok=True)
                
                file_path = os.path.join(data_dir, filename)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(watches, f, indent=2, ensure_ascii=False)
                
                self.stdout.write(self.style.SUCCESS(f'Raw data backup saved to {file_path}'))
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not save backup JSON: {str(e)}"))
            
            ref_count = sum(1 for watch in watches if watch.get('reference_number'))
            self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
            self.stdout.write(self.style.SUCCESS(f'SCRAPING SUMMARY:'))
            self.stdout.write(self.style.SUCCESS(f'- Pages scraped: {max_pages}'))
            self.stdout.write(self.style.SUCCESS(f'- Total items found: {len(watches)}'))
            self.stdout.write(self.style.SUCCESS(f'- Items with reference numbers: {ref_count}'))
            self.stdout.write(self.style.SUCCESS(f'- New items saved: {saved_count}'))
            self.stdout.write(self.style.SUCCESS(f'- Items skipped: {skipped_count}'))
            self.stdout.write(self.style.SUCCESS(f'{"="*60}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error in main handler: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())