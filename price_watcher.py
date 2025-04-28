#!/usr/bin/env python3
import os
import json
import time
import logging
import argparse
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PriceWatcher:
    def __init__(self, data_file='price_data.json', email_config=None):
        self.data_file = data_file
        self.items = {}
        self.email_config = email_config
        self.load_data()
        
    def load_data(self):
        """Load saved price data from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.items = json.load(f)
                logger.info(f"Loaded previous price data: {len(self.items)} items")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse {self.data_file}, starting with empty data")
                self.items = {}
        else:
            logger.info("No previous data file found, starting fresh")
    
    def save_data(self):
        """Save price data to file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.items, f, indent=2)
        logger.info(f"Saved price data: {len(self.items)} items")
    
    def add_item(self, url, name=None):
        """Add a new item to track"""
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            logger.error(f"Invalid URL format: {url}")
            return False
        
        item_id = url
        if item_id not in self.items:
            if not name:
                name = f"Item from {parsed_url.netloc}"
            
            self.items[item_id] = {
                "name": name,
                "url": url,
                "current_price": None,
                "previous_price": None,
                "last_checked": None
            }
            logger.info(f"Added new item to track: {name} ({url})")
            self.save_data()
            return True
        else:
            logger.info(f"Item already being tracked: {url}")
            return False
    
    def remove_item(self, url):
        """Remove an item from tracking"""
        if url in self.items:
            item_name = self.items[url]["name"]
            del self.items[url]
            logger.info(f"Removed item: {item_name} ({url})")
            self.save_data()
            return True
        else:
            logger.warning(f"Item not found: {url}")
            return False
    
    def list_items(self):
        """List all tracked items"""
        if not self.items:
            logger.info("No items currently being tracked")
            return []
        
        items_list = []
        for url, item in self.items.items():
            items_list.append({
                "name": item["name"],
                "url": url,
                "current_price": item["current_price"],
                "previous_price": item["previous_price"],
                "last_checked": item["last_checked"]
            })
        
        return items_list
    
    def check_prices(self):
        """Check prices for all tracked items"""
        logger.info("Starting price check")
        changes = []
        
        for url, item in self.items.items():
            # Verify the URL is still valid (no redirection)
            logger.info(f"Verifying product URL: {url}")
            try:
                head_response = requests.head(url, allow_redirects=False, timeout=10)
                if head_response.status_code in (301, 302, 303, 307, 308):
                    new_url = head_response.headers.get('Location')
                    if new_url:
                        logger.warning(f"URL has changed: {url} -> {new_url}")
                        changes.append({
                            "name": item["name"],
                            "url": url,
                            "change_type": "url",
                            "old_value": url,
                            "new_value": new_url,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        # Update the URL in our data
                        self.items[url]["previous_url"] = url
                        self.items[url]["url"] = new_url
            except requests.exceptions.RequestException as e:
                logger.error(f"Error checking URL redirection: {e}")
            
            # Check the price
            price = self.get_price(url, item["name"])
            
            if price is not None:
                # Update last checked timestamp
                item["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Check if this is the first time we're checking or if the price has changed
                if item["current_price"] is None:
                    logger.info(f"Initial price for {item['name']}: ${price}")
                    item["current_price"] = price
                elif price != item["current_price"]:
                    logger.info(f"Price change for {item['name']}: ${item['current_price']} -> ${price}")
                    item["previous_price"] = item["current_price"]
                    item["current_price"] = price
                    
                    # Record the change for notification
                    changes.append({
                        "name": item["name"],
                        "url": url,
                        "change_type": "price",
                        "old_value": item["previous_price"],
                        "new_value": price,
                        "timestamp": item["last_checked"]
                    })
                else:
                    logger.info(f"No price change for {item['name']}: ${price}")
            else:
                logger.warning(f"Could not retrieve price for {item['name']}")
        
        # Save updated data
        if changes:
            logger.info(f"Detected {len(changes)} changes")
            self.save_data()
            if self.email_config:
                self.send_notification(changes)
        else:
            logger.info("No price or URL changes detected")
            self.save_data()
        
        return changes
    
    def get_price(self, url, name):
        """Get the current price for a specific item"""
        logger.info(f"Fetching price for {name} ({url})")
        
        try:
            # First try a simple GET request with headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            response = requests.get(url, headers=headers, timeout=15)
            logger.info(f"Page fetched, status code: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different price selectors (Walmart specific)
                selectors = [
                    '[itemprop="price"]',
                    '.price-characteristic',
                    '[data-automation-id="price-value"]',
                    '.prod-PriceSection [aria-hidden="false"]',
                    'span.price-group',
                    # Try more specific Walmart selectors for the main product
                    '[data-testid="price-wrap"] span.inline-flex span.primary'
                ]
                
                for selector in selectors:
                    price_element = soup.select_one(selector)
                    if price_element:
                        price_text = price_element.get_text().strip()
                        logger.info(f"Found price with selector {selector}: {price_text}")
                        
                        # Extract numeric price value
                        price = self.extract_price(price_text)
                        if price is not None:
                            return price
                
                # If we didn't find a price with the selectors, try with Selenium
                return self.get_price_with_selenium(url)
            else:
                logger.error(f"Failed to fetch page, status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching price with requests: {e}")
            # Fall back to Selenium
            return self.get_price_with_selenium(url)
    
    def get_price_with_selenium(self, url):
        """Get price using Selenium for JavaScript-heavy sites"""
        logger.info("Falling back to Selenium for price extraction")
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        try:
            with webdriver.Chrome(options=options) as driver:
                driver.get(url)
                logger.info("Page loaded in Selenium")
                
                # Wait for page to fully load
                time.sleep(5)
                
                # Walmart-specific selectors for the main product (not sponsored)
                selectors = [
                    # Primary main product price
                    "div[data-testid='price-wrap'] span[itemprop='price']",
                    # Fallback selectors
                    "[data-automation-id='product-price']:not([data-automation-id*='sponsored'])",
                    "[data-testid='price-view'] span",
                    ".price-characteristic",
                    ".prod-PriceSection [aria-hidden='false']"
                ]
                
                for selector in selectors:
                    logger.info(f"Trying selector: {selector}")
                    try:
                        # Wait for element to be present
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        
                        # Get all matching elements
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        logger.info(f"Found {len(elements)} elements with selector {selector}")
                        
                        if elements:
                            # Prioritize the first element (usually the main product price)
                            price_text = elements[0].text.strip()
                            logger.info(f"Found price text: {price_text}")
                            print(f"current price {price_text}")  # Debug print
                            
                            # Extract numeric price
                            price = self.extract_price(price_text)
                            if price is not None:
                                return price
                    except TimeoutException:
                        continue
                    except Exception as e:
                        logger.error(f"Error with selector {selector}: {e}")
                
                # As a last resort, take a screenshot to debug
                try:
                    screenshot_path = f"debug_screenshot_{int(time.time())}.png"
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"Saved debug screenshot to {screenshot_path}")
                except Exception as e:
                    logger.error(f"Could not save screenshot: {e}")
                
                logger.warning("Could not find price with any selector")
                return None
        except Exception as e:
            logger.error(f"Error with Selenium: {e}")
            return None
        finally:
            logger.info("terminate chrome process...")
    
    def extract_price(self, price_text):
        """Extract numeric price from text"""
        # Remove currency symbols, commas, and other non-numeric characters
        try:
            # Handle various price formats
            price_text = price_text.replace(',', '')
            price_text = price_text.replace('$', '')
            
            # Extract first valid number
            import re
            match = re.search(r'(\d+\.\d+|\d+)', price_text)
            if match:
                return float(match.group(0))
            else:
                logger.warning(f"Could not extract price from: {price_text}")
                return None
        except Exception as e:
            logger.error(f"Error extracting price: {e}")
            return None
    
    def send_notification(self, changes):
        """Send email notification about price changes"""
        if not self.email_config:
            logger.warning("Email configuration not provided, skipping notification")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Price Watcher Alert: Price Changes Detected"
            msg["From"] = self.email_config["sender"]
            msg["To"] = self.email_config["recipient"]
            
            # Build plain text content
            text_content = "Price Watcher has detected the following changes:\n\n"
            for change in changes:
                if change["change_type"] == "price":
                    text_content += f"{change['name']}\n"
                    text_content += f"URL: {change['url']}\n"
                    text_content += f"Price changed: ${change['old_value']} -> ${change['new_value']}\n"
                    text_content += f"Detected at: {change['timestamp']}\n\n"
                elif change["change_type"] == "url":
                    text_content += f"{change['name']}\n"
                    text_content += f"URL has changed:\n"
                    text_content += f"Old: {change['old_value']}\n"
                    text_content += f"New: {change['new_value']}\n"
                    text_content += f"Detected at: {change['timestamp']}\n\n"
            
            # Build HTML content
            html_content = """
            <html>
            <body>
            <h2>Price Watcher Alert</h2>
            <p>The following changes have been detected:</p>
            """
            
            for change in changes:
                html_content += "<div style='margin-bottom: 20px; padding: 10px; border: 1px solid #ccc;'>"
                html_content += f"<h3>{change['name']}</h3>"
                
                if change["change_type"] == "price":
                    html_content += f"<p><a href='{change['url']}'>View Product</a></p>"
                    html_content += f"<p><strong>Price changed:</strong> ${change['old_value']} → ${change['new_value']}</p>"
                elif change["change_type"] == "url":
                    html_content += "<p><strong>URL has changed:</strong></p>"
                    html_content += f"<p>Old: <a href='{change['old_value']}'>{change['old_value']}</a></p>"
                    html_content += f"<p>New: <a href='{change['new_value']}'>{change['new_value']}</a></p>"
                
                html_content += f"<p><em>Detected at: {change['timestamp']}</em></p>"
                html_content += "</div>"
            
            html_content += """
            </body>
            </html>
            """
            
            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP_SSL(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.login(self.email_config["username"], self.email_config["password"])
                server.send_message(msg)
            
            logger.info(f"Sent notification email to {self.email_config['recipient']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Track prices of products online")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add item command
    add_parser = subparsers.add_parser("add", help="Add an item to track")
    add_parser.add_argument("url", help="URL of the product to track")
    add_parser.add_argument("--name", "-n", help="Name for the product (optional)")
    
    # Remove item command
    remove_parser = subparsers.add_parser("remove", help="Remove an item from tracking")
    remove_parser.add_argument("url", help="URL of the product to remove")
    
    # List items command
    subparsers.add_parser("list", help="List all tracked items")
    
    # Check prices command
    check_parser = subparsers.add_parser("check", help="Check prices for all tracked items")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up email configuration from environment variables
    email_config = None
    email_user = os.environ.get("EMAIL_USER")
    email_pass = os.environ.get("EMAIL_PASS")
    alert_to = os.environ.get("ALERT_TO")
    
    if email_user and email_pass and alert_to:
        email_config = {
            "sender": email_user,
            "recipient": alert_to,
            "smtp_server": "smtp.gmail.com",  # Assuming Gmail, adjust if needed
            "smtp_port": 465,
            "username": email_user,
            "password": email_pass
        }
        logger.info("Loaded email configuration from environment variables")
    
    # Initialize price watcher
    watcher = PriceWatcher(email_config=email_config)
    
    # Process command
    if args.command == "add":
        watcher.add_item(args.url, args.name)
    elif args.command == "remove":
        watcher.remove_item(args.url)
    elif args.command == "list":
        items = watcher.list_items()
        if items:
            print("\nTracked Items:")
            for i, item in enumerate(items, 1):
                print(f"{i}. {item['name']}")
                print(f"   URL: {item['url']}")
                print(f"   Current Price: ${item['current_price'] if item['current_price'] else 'Not checked yet'}")
                print(f"   Last Checked: {item['last_checked'] if item['last_checked'] else 'Never'}")
                print()
    elif args.command == "check" or args.command is None:
        # If no command provided, default to checking prices
        watcher.check_prices()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()