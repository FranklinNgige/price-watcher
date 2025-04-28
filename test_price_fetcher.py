#!/usr/bin/env python3
from requests_html import HTMLSession
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fetch_price(url):
    """Test fetching price from a URL with detailed debugging"""
    logger.info(f"Testing price fetch for {url}")
    
    session = HTMLSession()
    # Fetch the page with a more realistic user agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    
    r = session.get(url, headers=headers)
    logger.info(f"Page fetched, status code: {r.status_code}")
    
    # Render with more time and retries
    logger.info("Rendering page with JavaScript...")
    try:
        r.html.render(sleep=3, timeout=30, retries=2, wait=2)
        logger.info("Page rendered successfully")
    except Exception as e:
        logger.error(f"Error rendering page: {e}")
        logger.info("Continuing with what we have...")
    
    # List of selectors to try
    selectors = [
        "span[itemprop='price']",
        "span.price-characteristic",
        ".price-characteristic",
        "span.price-group",
        "[data-automation-id='product-price']",
        ".prod-PriceSection span.price-group",
        ".prod-PriceSection",
        ".price-display"
    ]
    
    # Try each selector
    for selector in selectors:
        logger.info(f"Trying selector: {selector}")
        try:
            elements = r.html.find(selector)
            logger.info(f"Found {len(elements)} elements with selector {selector}")
            
            if elements:
                for i, el in enumerate(elements[:3]):  # Show up to first 3 matches
                    logger.info(f"Element {i} text: '{el.text}'")
                    logger.info(f"Element {i} attrs: {el.attrs}")
                    
                    # Try to extract price from this element
                    txt = el.attrs.get("content") or el.text
                    if txt:
                        logger.info(f"Found potential price text: {txt}")
                        price_match = re.search(r'(\d+\.?\d*)', txt)
                        if price_match:
                            price = float(price_match.group(1))
                            logger.info(f"Extracted price: ${price}")
        except Exception as e:
            logger.error(f"Error with selector {selector}: {e}")
    
    # Fallback: look for any text with a dollar sign and a number
    logger.info("Trying fallback price extraction from all page text")
    try:
        # Get all text from the page
        all_text = r.html.text
        # Show a sample of the text
        logger.info(f"Page text sample: {all_text[:200]}...")
        
        # Find all dollar amounts
        price_matches = re.findall(r'\$(\d+\.?\d*)', all_text)
        if price_matches:
            logger.info(f"Found potential prices: {price_matches[:10]}")  # Show up to 10 matches
    except Exception as e:
        logger.error(f"Error in fallback extraction: {e}")
    
    logger.info("Test completed")

if __name__ == "__main__":
    # Test with your Walmart URL
    walmart_url = "https://www.walmart.com/ip/Time-Tru-Heirloom-Collection-Two-Tone-Ladies-Bracelet-Wristwatch-with-Crystal-Bezel/8888455520?classType=REGULAR"
    test_fetch_price(walmart_url)
    
    # Uncomment to test with a different retailer for comparison
    # amazon_url = "https://www.amazon.com/dp/B08DFPV5Y3/"
    # test_fetch_price(amazon_url)