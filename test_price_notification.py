#!/usr/bin/env python3
import os
import json
import tempfile
import logging
from price_watcher import PriceWatcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_test():
    # 1) Prepare a temporary data file
    tmp = tempfile.gettempdir()
    data_file = os.path.join(tmp, "test_price_data.json")
    if os.path.exists(data_file):
        os.remove(data_file)

    # 2) Configure a dummy email server (runs locally on port 1025)
    #    Start one with: python -m smtpd -c DebuggingServer -n localhost:1025
    email_cfg = {
        "sender":    "test@example.com",
        "recipient": "you@example.com",
        "smtp_server": "localhost",
        "smtp_port":   1025,
        "username":    "",     # not used by the debug server
        "password":    ""
    }

    # 3) Create the watcher, seed it with one item at price=100
    watcher = PriceWatcher(
        data_file=data_file,
        email_config=email_cfg,
        use_s3=False
    )
    test_url = "https://example.com/product"
    watcher.items = {
        test_url: {
            "name":           "Test Product",
            "url":            test_url,
            "current_price":  100.0,
            "previous_price": None,
            "last_checked":   None
        }
    }
    watcher.save_data()
    logger.info("Seeded test data with price 100.0")

    # 4) Monkey‑patch get_price to simulate a price drop to 80.0
    def fake_get_price(url, name):
        assert url == test_url
        logger.info("fake_get_price() called, returning 80.0")
        return 80.0

    watcher.get_price = fake_get_price

    # 5) Run the check — this should detect a change and send an email
    #    The DebuggingServer will print the SMTP conversation to your console.
    changes = watcher.check_prices()
    if not changes:
        logger.error("❌ No changes detected! Test FAILED.")
        return

    logger.info("✅ Detected changes, check your local SMTP debug console for the email message.")
    logger.info("Test complete.")

if __name__ == "__main__":
    run_test()
