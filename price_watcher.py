#!/usr/bin/env python3
import os
import json
import time
import logging
import argparse
import smtplib
import requests
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 15
SELENIUM_WAIT_TIME = 5
SCREENSHOT_DIR = "debug_screenshots"

class PriceWatcher:
    def __init__(self, data_file='price_data.json', email_config=None, use_s3=False):
        """Initialize the price watcher with optional S3 support"""
        self.data_file = data_file
        self.items = {}
        self.email_config = email_config
        self.use_s3 = use_s3
        
        # If using S3, initialize boto3 client
        if self.use_s3:
            try:
                import boto3
                self.s3_bucket = os.environ.get('BUCKET_NAME')
                if not self.s3_bucket:
                    logger.warning("BUCKET_NAME environment variable not set. Falling back to local storage.")
                    self.use_s3 = False
                else:
                    self.s3 = boto3.client('s3')
                    logger.info(f"Using S3 bucket: {self.s3_bucket}")
            except ImportError:
                logger.warning("boto3 not installed. Falling back to local storage.")
                self.use_s3 = False
        
        # Create screenshot directory if it doesn't exist
        if not os.path.exists(SCREENSHOT_DIR):
            os.makedirs(SCREENSHOT_DIR)
        
        self.load_data()
        
    def load_data(self):
        """Load saved price data from file or S3"""
        if self.use_s3 and self.s3_bucket:
            try:
                obj = self.s3.get_object(Bucket=self.s3_bucket, Key=self.data_file)
                self.items = json.load(io.BytesIO(obj['Body'].read()))
                logger.info(f"Loaded {len(self.items)} items from S3")
            except self.s3.exceptions.NoSuchKey:
                logger.info("No S3 data file yet, starting fresh")
                self.items = {}
            except Exception as e:
                logger.error(f"Error loading data from S3: {e}")
                self.items = {}
        else:
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
        """Save price data to file or S3"""
        if self.use_s3 and self.s3_bucket:
            try:
                data = json.dumps(self.items, indent=2).encode()
                self.s3.put_object(Bucket=self.s3_bucket, Key=self.data_file, Body=data)
                logger.info(f"Saved {len(self.items)} items to S3")
            except Exception as e:
                logger.error(f"Error saving data to S3: {e}")
        else:
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
            logger.info(f"Verifying product URL: {url}")
            try:
                head_response = requests.head(url, allow_redirects=False, timeout=DEFAULT_TIMEOUT)
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
                        self.items[url]["previous_url"] = url
                        self.items[url]["url"] = new_url
            except requests.exceptions.RequestException as e:
                logger.error(f"Error checking URL redirection: {e}")
            
            price = self.get_price(url, item["name"])
            
            if price is not None:
                item["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if item["current_price"] is None:
                    logger.info(f"Initial price for {item['name']}: ${price}")
                    item["current_price"] = price
                elif price != item["current_price"]:
                    logger.info(f"Price change for {item['name']}: ${item['current_price']} -> ${price}")
                    item["previous_price"] = item["current_price"]
                    item["current_price"] = price
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
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            logger.info(f"Page fetched, status code: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                selectors = [
                    '[itemprop="price"]',
                    '.price-characteristic',
                    '[data-automation-id="price-value"]',
                    '.prod-PriceSection [aria-hidden="false"]',
                    'span.price-group',
                    '[data-testid="price-wrap"] span.inline-flex span.primary'
                ]
                
                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        text = element.get_text().strip()
                        logger.info(f"Found price with selector {selector}: {text}")
                        price = self.extract_price(text)
                        if price is not None:
                            return price
                
                return self.get_price_with_selenium(url)
            else:
                logger.error(f"Failed to fetch page, status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching price with requests: {e}")
            return self.get_price_with_selenium(url)
    
    def get_price_with_selenium(self, url):
        """Get price using Selenium for JavaScript-heavy sites"""
        logger.info("Falling back to Selenium for price extraction")
        from webdriver_setup import get_chrome_driver
        
        driver = None
        try:
            driver = get_chrome_driver()
            driver.get(url)
            
            wait = WebDriverWait(driver, SELENIUM_WAIT_TIME)
            price_el = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                ','.join([
                    '[itemprop="price"]',
                    '.price-characteristic',
                    '[data-automation-id="price-value"]',
                    '.prod-PriceSection [aria-hidden="false"]',
                    'span.price-group',
                    '[data-testid="price-wrap"] span.inline-flex span.primary'
                ])
            )))
            
            price_text = price_el.text.strip()
            logger.info(f"Found price with Selenium: {price_text}")
            return self.extract_price(price_text)
        
        except Exception as e:
            logger.error(f"Error fetching price with Selenium: {e}")
            return None
        
        finally:
            if driver:
                driver.quit()
            self.cleanup_screenshots()
    
    def cleanup_screenshots(self, max_to_keep=5):
        """Clean up old screenshots, keeping only the most recent ones"""
        try:
            screenshots = [
                os.path.join(SCREENSHOT_DIR, f)
                for f in os.listdir(SCREENSHOT_DIR)
                if f.startswith("debug_screenshot_")
            ]
            if len(screenshots) > max_to_keep:
                screenshots.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                for old in screenshots[max_to_keep:]:
                    os.remove(old)
                    logger.debug(f"Removed old screenshot: {old}")
        except Exception as e:
            logger.error(f"Error cleaning up screenshots: {e}")
    
    def extract_price(self, price_text):
        """Extract numeric price from text"""
        try:
            price_text = price_text.replace(',', '').replace('$', '')
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
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Price Watcher Alert: Price Changes Detected"
            msg["From"] = self.email_config["sender"]
            msg["To"] = self.email_config["recipient"]
            
            # Build plain-text body
            text = "Price Watcher has detected the following changes:\n\n"
            for c in changes:
                text += f"{c['name']}\nURL: {c['url']}\n"
                if c["change_type"] == "price":
                    text += f"Price: ${c['old_value']} -> ${c['new_value']}\n"
                else:
                    text += f"URL: {c['old_value']} -> {c['new_value']}\n"
                text += f"At: {c['timestamp']}\n\n"
            
            # Build HTML body
            html = "<html><body><h2>Price Watcher Alert</h2>"
            for c in changes:
                html += "<div style='border:1px solid #ccc;padding:10px;margin:10px;'>"
                html += f"<h3>{c['name']}</h3>"
                if c["change_type"] == "price":
                    html += f"<p><strong>Price:</strong> ${c['old_value']} → ${c['new_value']}</p>"
                else:
                    html += f"<p><strong>URL:</strong> <a href='{c['new_value']}'>{c['new_value']}</a></p>"
                html += f"<p><em>At: {c['timestamp']}</em></p>"
                html += "</div>"
            html += "</body></html>"
            
            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))
            
            port = self.email_config["smtp_port"]
            host = self.email_config["smtp_server"]
            
            if port == 465:
                server = smtplib.SMTP_SSL(host, port)
                server.login(self.email_config["username"], self.email_config["password"])
            else:
                # plaintext SMTP (no SSL), e.g. localhost:1025 debug server
                server = smtplib.SMTP(host, port)
            
            with server:
                server.send_message(msg)
            
            logger.info(f"Sent notification email to {self.email_config['recipient']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Track prices of products online")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    add_p = subparsers.add_parser("add", help="Add an item to track")
    add_p.add_argument("url", help="URL of the product to track")
    add_p.add_argument("--name", "-n", help="Name for the product (optional)")
    
    rem_p = subparsers.add_parser("remove", help="Remove an item from tracking")
    rem_p.add_argument("url", help="URL of the product to remove")
    
    subparsers.add_parser("list", help="List all tracked items")
    check_p = subparsers.add_parser("check", help="Check prices for all tracked items")
    parser.add_argument("--s3", action="store_true", help="Use S3 for storage instead of local files")
    
    args = parser.parse_args()
    
    email_user = os.environ.get("EMAIL_USER")
    email_pass = os.environ.get("EMAIL_PASS")
    alert_to   = os.environ.get("ALERT_TO")
    email_cfg = None
    if email_user and email_pass and alert_to:
        email_cfg = {
            "sender":      email_user,
            "recipient":   alert_to,
            "smtp_server": "smtp.gmail.com",
            "smtp_port":   465,
            "username":    email_user,
            "password":    email_pass
        }
        logger.info("Loaded email configuration from environment")
    
    watcher = PriceWatcher(email_config=email_cfg, use_s3=args.s3)
    
    if args.command == "add":
        watcher.add_item(args.url, args.name)
    elif args.command == "remove":
        watcher.remove_item(args.url)
    elif args.command == "list":
        for i, itm in enumerate(watcher.list_items(), 1):
            print(f"{i}. {itm['name']}: {itm['url']} — Current: {itm['current_price']}, Last checked: {itm['last_checked']}")
    else:  # check or no command
        watcher.check_prices()

if __name__ == "__main__":
    main()
