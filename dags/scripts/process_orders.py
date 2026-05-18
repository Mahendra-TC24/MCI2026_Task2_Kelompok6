"""
process_orders.py
Script untuk mentransformasi (flatten) data orders dari format
nested JSON menjadi dua tabel datar:

  1. orders       — satu baris per order
  2. order_items  — satu baris per produk dalam order

Input  : /tmp/orders_raw.json   (hasil fetch_orders.py)
Output : /tmp/orders_flat.json
         /tmp/order_items_flat.json
"""

import json
import logging
import os
from datetime import datetime

#Konfigurasi
RAW_PATH        = os.getenv("RAW_PATH",   "/tmp/orders_raw.json")
ORDERS_OUT      = os.getenv("ORDERS_OUT", "/tmp/orders_flat.json")
ITEMS_OUT       = os.getenv("ITEMS_OUT",  "/tmp/order_items_flat.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Mapping order_dow (int) → nama hari
DOW_MAP = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}


#Helper
def safe_float(val, default=None):
    """Konversi ke float; kembalikan default jika None/NaN."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    """Konversi ke int; kembalikan default jika gagal."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


#Transform
def flatten_orders(raw_path: str = RAW_PATH,
                   orders_out: str = ORDERS_OUT,
                   items_out: str = ITEMS_OUT) -> dict:
    """
    Flatten nested orders JSON menjadi dua tabel CSV-ready.

    Returns:
        dict dengan jumlah baris masing-masing tabel
    """
    logging.info(f"Membaca raw data dari: {raw_path}")
    with open(raw_path, encoding="utf-8") as f:
        payload = json.load(f)

    # Normalisasi struktur
    raw_orders = (
        payload if isinstance(payload, list)
        else payload.get("orders", [])
    )

    flat_orders = []
    flat_items  = []

    for o in raw_orders:
        order_id = safe_int(o.get("order_id"))
        user_id  = safe_int(o.get("user_id"))
        products = o.get("products", [])
        dow      = safe_int(o.get("order_dow", 0))

        #Baris tabel orders
        flat_orders.append({
            "order_id":               order_id,
            "user_id":                user_id,
            "order_number":           safe_int(o.get("order_number")),
            "order_dow":              dow,
            "order_dow_name":         DOW_MAP.get(dow, "Unknown"),
            "order_hour_of_day":      safe_int(o.get("order_hour_of_day")),
            "days_since_prior_order": safe_float(o.get("days_since_prior_order")),  # nullable
            "eval_set":               str(o.get("eval_set", "prior")),
            "total_items":            len(products),
            "total_reordered":        sum(
                                          1 for p in products
                                          if safe_int(p.get("reordered")) == 1
                                      ),
        })

        #Baris tabel order_items
        for p in products:
            flat_items.append({
                "order_id":          order_id,
                "user_id":           user_id,
                "product_id":        safe_int(p.get("product_id")),
                "product_name":      str(p.get("product_name", "")).strip(),
                "aisle_id":          safe_int(p.get("aisle_id")),
                "aisle":             str(p.get("aisle", "")).strip(),
                "department_id":     safe_int(p.get("department_id")),
                "department":        str(p.get("department", "")).strip(),
                "add_to_cart_order": safe_int(p.get("add_to_cart_order")),
                "reordered":         safe_int(p.get("reordered")),
            })

    # Simpan hasil
    with open(orders_out, "w", encoding="utf-8") as f:
        json.dump(flat_orders, f, ensure_ascii=False)

    with open(items_out, "w", encoding="utf-8") as f:
        json.dump(flat_items, f, ensure_ascii=False)

    logging.info(f"orders flat      → {len(flat_orders)} baris  ({orders_out})")
    logging.info(f"order_items flat → {len(flat_items)} baris ({items_out})")

    return {
        "order_count":      len(flat_orders),
        "order_item_count": len(flat_items),
        "processed_at":     datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    result = flatten_orders()
    print(json.dumps(result, indent=2))
