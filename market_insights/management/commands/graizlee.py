import os
import json
import time
import re
from datetime import datetime
from decimal import Decimal
import tempfile
import uuid
from django.core.management.base import BaseCommand
from market_insights.models import MarketData
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


class Command(BaseCommand):
    help = 'Scrapes watch data from Grailzee.com and saves to MarketData model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max_items',
            type=int,
            default=200,
            help='Maximum number of items to scrape'
        )

    def extract_reference_number(self, model_text):
        """
        Extract reference number from model text using multiple patterns
        
        Args:
            model_text: The model text string to extract from
        
        Returns:
            Reference number string or None
        """
        if not model_text:
            return None
            
        # Pattern 1: Standard reference with dash and 4 digits (e.g. "178243-0077")
        pattern1 = r'[A-Z0-9]+-\d{4}'
        match = re.search(pattern1, model_text)
        if match:
            return match.group(0)
        
        # Pattern 2: Rolex style references (e.g. "116610LN")
        pattern2 = r'\b\d{6}[A-Z]{0,2}\b'
        match = re.search(pattern2, model_text)
        if match:
            return match.group(0)
        
        # Pattern 3: References with dots (e.g. "03.3107.3600/56.M3100" or "212.30.41.20.01.002")
        pattern3 = r'\d+(?:\.\d+){2,}'
        match = re.search(pattern3, model_text)
        if match:
            return match.group(0)
        
        # Pattern 4: Last word if it contains numbers and letters (likely a reference)
        words = model_text.split()
        last_word = words[-1] if words else ""
        if re.search(r'^[A-Z0-9]+$', last_word) and re.search(r'\d', last_word) and re.search(r'[A-Z]', last_word):
            return last_word
        
        return None

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

    def scrape_grailzee_watches(self, max_items=200, initial_scroll_pause=4):
        """
        Scrape watches from Grailzee.com with improved infinite scroll handling
        
        Args:
            max_items: Maximum number of items to scrape
            initial_scroll_pause: Initial time to pause between scrolls in seconds
        
        Returns:
            List of watch dictionaries
        """
        # Setup Chrome with anti-detection measures
        options = Options()
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        # options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Create a unique user data directory with UUID to ensure it's not already in use
        unique_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{uuid.uuid4().hex}")
        options.add_argument(f"--user-data-dir={unique_dir}")
        
        driver = webdriver.Chrome(options=options)
        
        # Mask WebDriver
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        watches_data = []
        
        try:
            # Load the page with filter for popular brands
            url = 'https://grailzee.com/pages/completed-auctions?makes=rolex%2Comega%2Cbreitling%2Ctudor%2Cpanerai%2Ctag-heuer%2Chublot%2Ccartier%2Caudemars-piguet%2Cpatek-philippe%2Cfranck-muller%2Cglashutte&sort=1'
            driver.get(url)
            self.stdout.write(f"Loading URL: {url}")
            
            # Wait for page to load completely
            time.sleep(7)  # Increased initial wait time
            
            # Handle cookie consent if it appears
            try:
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'cookie') or contains(text(), 'Accept')]")
                if cookie_buttons:
                    cookie_buttons[0].click()
                    self.stdout.write("Clicked cookie consent button")
                    time.sleep(3)  # Wait longer after clicking cookie consent
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Cookie handling error: {str(e)}"))
            
            # Variables for scroll tracking
            scroll_attempts = 0
            max_scroll_attempts = 150  # Increased max attempts
            previous_item_count = 0
            no_new_items_count = 0
            scroll_pause_time = initial_scroll_pause  # Start with initial pause time
            
            # Get window height for incremental scrolling
            window_height = driver.execute_script("return window.innerHeight")
            total_height = driver.execute_script("return document.body.scrollHeight")
            current_position = 0
            
            while len(watches_data) < max_items and scroll_attempts < max_scroll_attempts:
                # Check for popups before each scroll
                self.check_and_close_popup(driver)
                
                # Get current page content
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Find watch listing items 
                model_cards = soup.find_all('div', class_='auction-cell col-xl-4 col-lg-4 col-md-6 col-sm-6 col-12')
                
                # Process each card we haven't processed yet
                current_item_count = len(model_cards)
                self.stdout.write(f"Found {current_item_count} items so far")
                
                # Check if we got new items
                if current_item_count <= previous_item_count:
                    no_new_items_count += 1
                    
                    # If stuck, try clicking any "Load more" buttons
                    try:
                        load_more_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Load more') or contains(text(), 'Show more')]")
                        if load_more_buttons:
                            for button in load_more_buttons:
                                if button.is_displayed():
                                    button.click()
                                    self.stdout.write("Clicked 'Load more' button")
                                    time.sleep(3)  # Longer wait after clicking Load More
                                    no_new_items_count = 0  # Reset counter since we took an action
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Error clicking load more: {str(e)}"))
                    
                    # Try a middle scroll instead of bottom scroll if we're stuck
                    if no_new_items_count == 2:
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.7);")
                        self.stdout.write("Trying a partial scroll")
                        time.sleep(scroll_pause_time * 1.5)  # Wait longer for partial scroll
                        
                        # Refresh scroll height
                        total_height = driver.execute_script("return document.body.scrollHeight")
                        
                    # Increase pause time if we're struggling to get new items
                    scroll_pause_time = min(10, scroll_pause_time + 0.5)  # Gradually increase up to 10 seconds
                    self.stdout.write(f"Increased scroll pause time to {scroll_pause_time}s")
                    
                    if no_new_items_count >= 4:  # More patience before giving up
                        self.stdout.write("No new items found after 4 scrolls. Stopping.")
                        break
                else:
                    no_new_items_count = 0
                    
                previous_item_count = current_item_count
                
                # Process new cards
                start_index = len(watches_data)
                for i in range(start_index, len(model_cards)):
                    if i >= len(model_cards):
                        break

                    try:
                        # Extract data from each watch card
                        card = model_cards[i]
                        
                        # Find elements properly using BeautifulSoup methods
                        title_tag = card.select_one('.card-title a')
                        title_text = title_tag.text.strip() if title_tag else ''
                        
                        # Extract brand from title - Usually the first word
                        brand = None
                        if title_text:
                            title_words = title_text.split()
                            if title_words:
                                brand = title_words[0]
                        
                        # Extract reference number from title
                        reference_number = self.extract_reference_number(title_text)
                        
                        # Find image
                        image = card.select_one('.auction-image img')
                        image_url = ''
                        if image and image.has_attr('src'):
                            image_url = image['src']
                        elif image and image.has_attr('data-src'):
                            image_url = image['data-src']
                        
                        # Make URL absolute if needed
                        if image_url and not image_url.startswith('http'):
                            image_url = 'https://grailzee.com' + image_url
                        
                        # Find link
                        link_tag = card.select_one('a.auction-link')
                        link_url = ''
                        if link_tag and link_tag.has_attr('href'):
                            link_url = link_tag['href']
                            # Make URL absolute if needed
                            if link_url and not link_url.startswith('http'):
                                link_url = 'https://grailzee.com' + link_url
                        
                        # Find price info
                        price_value = None
                        price_tag = card.select_one('.auction-current-bid')
                        if price_tag:
                            full_text = price_tag.get_text(separator=' ', strip=True)
                            price_match = re.search(r'\$\d{1,3}(?:,\d{3})*', full_text)
                            if price_match:
                                price_str = price_match.group().replace('$', '').replace(',', '')
                                try:
                                    price_value = int(price_str)
                                except (ValueError, TypeError):
                                    price_value = None
                        
                        # Extract condition info
                        condition = None
                        condition_tag = card.select_one('.auction-condition')
                        if condition_tag:
                            condition = condition_tag.get_text(strip=True)
                        
                        # Generate an item_id (we need something unique for the database)
                        # Use combination of brand, title and price if possible
                        unique_parts = []
                        if brand:
                            unique_parts.append(brand.replace(' ', '_'))
                        if title_text:
                            # Only use first 30 chars to prevent overly long IDs
                            unique_parts.append(title_text[:30].replace(' ', '_'))
                        if price_value:
                            unique_parts.append(str(price_value))
                        
                        # Create a unique item_id
                        item_id = "grailzee_" + "_".join(unique_parts)
                        if not item_id or item_id == "grailzee_":
                            # Fallback to timestamp if we couldn't create a better id
                            item_id = f"grailzee_{int(time.time())}_{len(watches_data)}"
                        
                        # Build watch dictionary
                        watch = {
                            'brand': brand,
                            'title': title_text,
                            'model': title_text,
                            'listing_url': link_url,
                            'price': price_value,
                            'reference_number': reference_number,
                            'image_url': image_url,
                            'item_id': item_id,
                            'condition': condition
                        }
                        
                        watches_data.append(watch)
                        if len(watches_data) >= max_items:
                            self.stdout.write(f"Reached maximum item limit of {max_items}")
                            break
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing card {i}: {str(e)}"))
                
                # If we've reached the target number of items, break
                if len(watches_data) >= max_items:
                    break
                    
                # Implement smooth, incremental scrolling
                scroll_attempts += 1
                
                # Refresh the total height measurement
                total_height = driver.execute_script("return document.body.scrollHeight")
                
                # Use incremental scrolling for better loading
                if scroll_attempts % 3 == 0:
                    # Every 3rd attempt, go to the bottom to force load
                    current_position = total_height
                    driver.execute_script(f"window.scrollTo(0, {total_height});")
                    self.stdout.write(f"Full scroll to bottom (height: {total_height}px)")
                else:
                    # Otherwise do incremental scrolling
                    # Scroll by 1.5x the window height each time
                    scroll_increment = int(window_height * 1.5)
                    new_position = min(current_position + scroll_increment, total_height)
                    
                    # Perform smooth scrolling with multiple small steps
                    steps = 5
                    for i in range(1, steps + 1):
                        intermediate_position = current_position + (scroll_increment * i / steps)
                        driver.execute_script(f"window.scrollTo(0, {intermediate_position});")
                        time.sleep(0.5)  # Short pause between incremental scrolls
                    
                    current_position = new_position
                    self.stdout.write(f"Incremental scroll to position {current_position}px of {total_height}px")
                
                # Wait after scrolling to allow content to load
                self.stdout.write(f"Waiting {scroll_pause_time}s for content to load...")
                time.sleep(scroll_pause_time)
                
                # Additional check for new content by checking if height changed
                new_total_height = driver.execute_script("return document.body.scrollHeight")
                if new_total_height > total_height:
                    self.stdout.write(f"Page height increased: {total_height}px -> {new_total_height}px")
                    total_height = new_total_height
                    # Reset no_new_items_count since the page height changed
                    no_new_items_count = max(0, no_new_items_count - 1)
                
                # Check for popups after scrolling
                self.check_and_close_popup(driver)
                time.sleep(1.5)  # Wait a bit longer after closing popup
                
                # Print progress every 5 scrolls
                if scroll_attempts % 5 == 0:
                    self.stdout.write(f"Scroll attempt #{scroll_attempts}, items collected: {len(watches_data)}")
                    self.stdout.write(f"Current scroll pause time: {scroll_pause_time}s")
            
            self.stdout.write(f"Finished after {scroll_attempts} scroll attempts")
            
            # Generate reference number success rate stats
            refs_found = sum(1 for watch in watches_data if watch.get('reference_number'))
            if watches_data:
                ref_success_rate = (refs_found / len(watches_data)) * 100
                self.stdout.write(f"Reference numbers extracted: {refs_found}/{len(watches_data)} ({ref_success_rate:.1f}%)")
            
            return watches_data
        
        finally:
            # Close the browser
            driver.quit()

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Grailzee watch data extraction...'))
        
        max_items = options['max_items']
        
        try:
            # Scrape data from Grailzee
            watches = self.scrape_grailzee_watches(max_items=max_items)
            self.stdout.write(self.style.SUCCESS(f"Successfully scraped {len(watches)} watches"))
            
            # Count items with images
            items_with_images = sum(1 for watch in watches if watch.get('image_url'))
            if watches:
                percentage = (items_with_images/len(watches))*100
                self.stdout.write(f"Items with images: {items_with_images}/{len(watches)} ({percentage:.1f}%)")
            
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
                    source='grailzee',
                    price=price_value,
                    item_id=item_id,
                    name=watch.get('title'),
                    image_url=watch.get('image_url'),
                    listing_url=watch.get('listing_url'),
                    reference_number=watch.get('reference_number'),
                    brand=watch.get('brand'),
                    condition=watch.get('condition')
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
            filename = f"grailzee_watches_{timestamp}.json"
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(watches, f, indent=2, ensure_ascii=False)
            
            self.stdout.write(self.style.SUCCESS(f'Saved {saved_count} new items to database, skipped {skipped_count} items'))
            self.stdout.write(self.style.SUCCESS(f'Raw data backup saved to {filename}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during scraping: {str(e)}"))