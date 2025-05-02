#!/usr/bin/env python3

from price_watcher import PriceWatcher

def main():
    watcher = PriceWatcher()

    # Add your items
    watcher.add_item(
        "https://www.amazon.com/Apple-iPad-11-inch-Display-All-Day/dp/B0DZ77D5HL/"
        "?_encoding=UTF8&pd_rd_w=gZPEG&content-id=amzn1.sym."
        "f2128ffe-3407-4a64-95b5-696504f68ca1&pf_rd_p=f2128ffe-3407-4a64-95b5-696504f68ca1"
        "&pf_rd_r=CDH1437VJ2THDWK707QB&pd_rd_wg=FSaoY&pd_rd_r=59481865-efc1-42ae-"
        "82f0-e3c4f0c78e79&ref_=pd_hp_d_btf_crs_zg_bs_541966&th=1",
        "Apple iPad 11‑inch Display (All‑Day Battery)"
    )

    watcher.add_item(
        "https://www.walmart.com/ip/Time-Tru-Women-s-Hazel-Satchel-Bag-Seafoam/"
        "11607861671?athAsset=eyJhdGhjcGlkIjoiMTE2MDc4NjE2NzEiLCJhdGhzdGlkIjoi"
        "Q1MwMjAiLCJhdGhhbmNpZCI6IlByaXNtQ29sbGVjdGlvbkNhcm91c2VsIiwiYXRocmsi"
        "OjAuMH0=&athena=true",
        "Time Tru Women’s Hazel Satchel Bag (Seafoam)"
    )

    # Add more items as needed...
    
    print("Items added successfully!")

if __name__ == "__main__":
    main()
