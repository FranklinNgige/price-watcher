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

    watcher.add_item(
        "https://www.amazon.com/Insta360-Waterproof-Replaceable-Built-Stabilization/dp/B0DZCBYCNY/"
        "ref=sr_1_1?crid=1KENFC3IND2ES&dib=eyJ2IjoiMSJ9.KZX0ewnf_2RHHNcaG7rR6OO4DZmqUG6-"
        "LrE45Iy9LYVNS1_zuQYbqKvnDhkpm_g04A7iCSjCRsnD1jIV9l4JnIgNXLkuNKGEPVSipcIF6smFM23y4o"
        "Mpav7JK_uHTSnKdKF1FJropDvH43sG6AJdoze8kw8tzCuWk09YKt2wQJE5fFm9IgziFZ1q0PiEO50."
        "Z-ObwUQOeP39qphJIp1_Ht45Ud8kX2zToHZOb9nJt-g&dib_tag=se&keywords=insta360x5%2Bcamera"
        "&qid=1746290801&sprefix=insta360x5%2Caps%2C131&sr=8-1&th=1",
        "Insta360 Waterproof Replaceable Built-Stabilization"
    )


    # Add more items as needed...
    
    print("Items added successfully!")

if __name__ == "__main__":
    main()
